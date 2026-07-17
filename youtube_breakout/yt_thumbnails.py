#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import urllib.request
from http.client import HTTPMessage
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .common import (
    THUMBNAILS_DIR,
    day_stamp,
    latest_search_bundle,
    now_utc,
    public_path_label,
    read_json,
    safe_child_path,
    time_slug,
    validate_path_slug,
    write_json,
    write_text,
)

ALLOWED_THUMBNAIL_HOSTS = {"i.ytimg.com", "img.youtube.com"}
MAX_THUMBNAIL_BYTES = 5 * 1024 * 1024
ACCEPTED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


class ThumbnailDownloadError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and analyze thumbnails for top YouTube radar candidates.")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--timeout-sec", type=float, default=20)
    parser.add_argument("--out")
    return parser.parse_args()


def candidate_videos(days: int, top: int) -> list[dict[str, Any]]:
    """Select thumbnail candidates from the latest local search bundle.

    Dates are used when present; unknown dates stay eligible but are not upgraded.
    """
    bundle_path = latest_search_bundle()
    if not bundle_path:
        return []
    payload = read_json(bundle_path)
    rows = list(payload.get("videos") or [])
    rows.sort(
        key=lambda row: (
            int(row.get("views") or 0),
            int(row.get("comments_count") or 0),
        ),
        reverse=True,
    )
    return rows[:top]


def safe_file_stem(item: dict[str, Any]) -> str:
    key = item.get("video_id") or item.get("video_url") or item.get("title") or "thumbnail"
    digest = hashlib.sha1(str(key).encode("utf-8")).hexdigest()[:10]
    video_id = validate_path_slug(item.get("video_id") or digest, field="video_id")
    return f"{video_id}-{digest}"


def thumbnail_url_for_item(item: dict[str, Any]) -> str | None:
    existing = item.get("thumbnail_url")
    if existing:
        return existing
    video_id = item.get("video_id")
    if video_id:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return None


def thumbnail_host_allowed(hostname: str | None) -> bool:
    host = (hostname or "").lower().rstrip(".")
    return host in ALLOWED_THUMBNAIL_HOSTS or bool(re_full_i_ytimg(host))


def re_full_i_ytimg(host: str) -> bool:
    return host.startswith("i") and host.endswith(".ytimg.com") and host[1:-10].isdigit()


def validate_thumbnail_url(url: str, *, error_code: str = "unsafe_thumbnail_url") -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ThumbnailDownloadError(error_code, "thumbnail URL must use HTTPS")
    if parsed.username or parsed.password:
        raise ThumbnailDownloadError(error_code, "thumbnail URL must not include credentials")
    if not thumbnail_host_allowed(parsed.hostname):
        raise ThumbnailDownloadError(error_code, "thumbnail URL host is not allowed")
    return url


class ValidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        validate_thumbnail_url(newurl, error_code="unsafe_redirect_url")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_thumbnail_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(ValidatingRedirectHandler)


def response_content_type(headers: HTTPMessage | Any) -> str:
    raw = ""
    if hasattr(headers, "get_content_type"):
        raw = headers.get_content_type()
    elif hasattr(headers, "get"):
        raw = headers.get("Content-Type", "")
    return str(raw or "").split(";", 1)[0].strip().lower()


def read_capped(response: Any, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ThumbnailDownloadError("thumbnail_too_large", f"thumbnail exceeds {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def valid_image_bytes(content: bytes, content_type: str) -> bool:
    if content_type in {"image/jpeg", "image/jpg"}:
        return content.startswith(b"\xff\xd8")
    if content_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return False


def download_thumbnail(url: str, target: Path, timeout_sec: float, max_bytes: int = MAX_THUMBNAIL_BYTES) -> dict[str, Any]:
    validate_thumbnail_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 YouTubeRadar/1.0"})
    with build_thumbnail_opener().open(req, timeout=timeout_sec) as response:
        final_url = getattr(response, "url", url)
        validate_thumbnail_url(final_url, error_code="unsafe_redirect_url")
        content_type = response_content_type(response.headers)
        if content_type not in ACCEPTED_IMAGE_TYPES:
            raise ThumbnailDownloadError("invalid_content_type", f"unsupported thumbnail content type: {content_type or 'missing'}")
        content = read_capped(response, max_bytes)
    if not valid_image_bytes(content, content_type):
        raise ThumbnailDownloadError("invalid_image_bytes", "thumbnail response is not a valid supported image")
    target.write_bytes(content)
    return {
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "content_type": content_type,
        "source_url": url,
        "final_url": final_url,
    }


def image_metrics_with_external_pillow(path: Path) -> dict[str, Any] | None:
    """No hidden interpreter fallback: optional Pillow must be installed in this environment."""
    return None


def image_metrics(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image, ImageFilter, ImageStat
    except Exception as exc:
        helper_metrics = image_metrics_with_external_pillow(path)
        if helper_metrics:
            return helper_metrics
        return {
            "status": "visual_metrics_unavailable",
            "reason": f"Pillow unavailable: {str(exc)[:160]}",
            "labels": ["image-downloaded/no-local-vision"],
        }

    try:
        with Image.open(path) as img:
            rgb = img.convert("RGB")
            width, height = rgb.size
            small = rgb.resize((160, 90)) if width >= height else rgb.resize((90, 160))
            gray = small.convert("L")
            hsv = small.convert("HSV")
            stat_gray = ImageStat.Stat(gray)
            stat_hsv = ImageStat.Stat(hsv)
            brightness = round(stat_gray.mean[0], 2)
            contrast = round(stat_gray.stddev[0], 2)
            saturation = round(stat_hsv.mean[1], 2)
            edge = gray.filter(ImageFilter.FIND_EDGES)
            edge_mean = round(ImageStat.Stat(edge).mean[0], 2)
            pixels = list(small.getdata())
            rg_values = [r - g for r, g, b in pixels]
            yb_values = [0.5 * (r + g) - b for r, g, b in pixels]
            rg_mean = sum(rg_values) / len(rg_values)
            yb_mean = sum(yb_values) / len(yb_values)
            rg_std = math.sqrt(sum((x - rg_mean) ** 2 for x in rg_values) / len(rg_values))
            yb_std = math.sqrt(sum((x - yb_mean) ** 2 for x in yb_values) / len(yb_values))
            colorfulness = round(math.sqrt(rg_std**2 + yb_std**2) + 0.3 * math.sqrt(rg_mean**2 + yb_mean**2), 2)
            return {
                "status": "ok",
                "width": width,
                "height": height,
                "aspect_ratio": round(width / height, 3) if height else None,
                "brightness": brightness,
                "contrast": contrast,
                "saturation": saturation,
                "edge_density_proxy": edge_mean,
                "colorfulness": colorfulness,
                "labels": visual_labels(brightness, contrast, saturation, edge_mean, colorfulness),
            }
    except Exception as exc:
        return {
            "status": "visual_metrics_error",
            "reason": str(exc)[:160],
            "labels": ["image-downloaded/analysis-error"],
        }


def visual_labels(brightness: float, contrast: float, saturation: float, edge_mean: float, colorfulness: float) -> list[str]:
    labels: list[str] = []
    if contrast >= 60:
        labels.append("high-contrast")
    elif contrast <= 32:
        labels.append("low-contrast")
    if saturation >= 110 or colorfulness >= 70:
        labels.append("saturated/color-pop")
    if brightness <= 70:
        labels.append("dark")
    elif brightness >= 185:
        labels.append("bright")
    if edge_mean >= 32:
        labels.append("dense/text-or-detail-heavy")
    elif edge_mean <= 14:
        labels.append("clean/simple")
    return labels or ["neutral"]


def analyze_items(items: list[dict[str, Any]], run_dir: Path, timeout_sec: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    images_dir = run_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    for rank, item in enumerate(items, start=1):
        thumb_url = thumbnail_url_for_item(item)
        row = {
            "rank": rank,
            "video_id": item.get("video_id"),
            "title": item.get("title"),
            "channel_name": item.get("channel_name"),
            "video_url": item.get("video_url"),
            "thumbnail_url": thumb_url,
            "content_decision": item.get("content_decision"),
            "local_growth_score": item.get("local_growth_score"),
            "title_patterns": item.get("title_patterns") or [],
            "outlier_metrics": item.get("outlier_metrics") or {},
            "status": "missing_thumbnail_url",
        }
        if not thumb_url:
            rows.append(row)
            continue
        suffix = ".jpg" if ".jpg" in thumb_url.lower() or ".jpeg" in thumb_url.lower() else ".webp" if ".webp" in thumb_url.lower() else ".png"
        target = safe_child_path(images_dir, f"{rank:02d}-{safe_file_stem(item)}{suffix}", field="thumbnail filename")
        try:
            file_meta = download_thumbnail(thumb_url, target, timeout_sec)
            metrics = image_metrics(target)
            row.update({
                "status": "ok",
                "local_path": public_path_label(target),
                "file": file_meta,
                "visual_metrics": metrics,
            })
        except ThumbnailDownloadError as exc:
            row.update({"status": "degraded", "error_code": exc.code, "error": str(exc)[:300]})
        except Exception as exc:
            row.update({"status": "error", "error_code": "thumbnail_download_error", "error": str(exc)[:300]})
        rows.append(row)
    return rows


def render_markdown(rows: list[dict[str, Any]], generated_at: str) -> str:
    lines = ["# YouTube Thumbnail Visual Scan", "", f"- Generated at: {generated_at}", f"- Items: {len(rows)}", ""]
    lines.append("## Top thumbnail signals")
    for row in rows:
        metrics = row.get("visual_metrics") or {}
        labels = ", ".join(metrics.get("labels") or []) if metrics else row.get("status")
        lines.append(
            f"- #{row['rank']} **{row.get('title') or 'Untitled'}** | growth: {row.get('local_growth_score')} | "
            f"decision: {row.get('content_decision')} | labels: {labels} | "
            f"brightness: {metrics.get('brightness')} | contrast: {metrics.get('contrast')} | "
            f"saturation: {metrics.get('saturation')} | image: {row.get('local_path') or 'n/a'}"
        )
    lines.append("")
    lines.append("## Caveat")
    lines.append("- Это локальный визуальный слой: цвет/контраст/детальность/thumbnail asset. Не OCR и не распознавание лиц. Для этого нужен следующий optional vision pass.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    generated_at = now_utc().replace(microsecond=0).isoformat()
    run_dir = THUMBNAILS_DIR / day_stamp() / time_slug()
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = analyze_items(candidate_videos(args.days, args.top), run_dir, args.timeout_sec)
    manifest_path = Path(args.out) if args.out else run_dir / "thumbnail-analysis.json"
    write_json(manifest_path, {"generated_at": generated_at, "items": rows})
    md_path = run_dir / "thumbnail-analysis.md"
    write_text(md_path, render_markdown(rows, generated_at))
    latest_path = THUMBNAILS_DIR / "latest.json"
    write_json(latest_path, {
        "generated_at": generated_at,
        "manifest_path": public_path_label(manifest_path),
        "markdown_path": public_path_label(md_path),
        "items": rows,
    })
    print(public_path_label(manifest_path))
    print(public_path_label(md_path))


if __name__ == "__main__":
    main()
