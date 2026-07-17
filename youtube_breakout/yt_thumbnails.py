#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

from .common import (
    THUMBNAILS_DIR,
    day_stamp,
    latest_search_bundle,
    now_utc,
    read_json,
    time_slug,
    write_json,
    write_text,
)


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
    video_id = item.get("video_id") or digest
    return f"{video_id}-{digest}"


def thumbnail_url_for_item(item: dict[str, Any]) -> str | None:
    existing = item.get("thumbnail_url")
    if existing:
        return existing
    video_id = item.get("video_id")
    if video_id:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return None


def download_thumbnail(url: str, target: Path, timeout_sec: float) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 YouTubeRadar/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_sec) as response:
        content = response.read()
    target.write_bytes(content)
    return {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


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
        suffix = ".jpg" if ".jpg" in thumb_url.lower() or ".jpeg" in thumb_url.lower() else ".webp" if ".webp" in thumb_url.lower() else ".img"
        target = images_dir / f"{rank:02d}-{safe_file_stem(item)}{suffix}"
        try:
            file_meta = download_thumbnail(thumb_url, target, timeout_sec)
            metrics = image_metrics(target)
            row.update({
                "status": "ok",
                "local_path": str(target),
                "file": file_meta,
                "visual_metrics": metrics,
            })
        except Exception as exc:
            row.update({"status": "error", "error": str(exc)[:300]})
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
    write_json(latest_path, {"generated_at": generated_at, "manifest_path": str(manifest_path), "markdown_path": str(md_path), "items": rows})
    print(str(manifest_path))
    print(str(md_path))


if __name__ == "__main__":
    main()
