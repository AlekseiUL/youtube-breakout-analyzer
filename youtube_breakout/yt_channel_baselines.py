#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from statistics import median
from typing import Any

from .common import (
    CHANNEL_BASELINES_DIR,
    WATCHLISTS_DIR,
    latest_search_bundle,
    load_channel_watchlist,
    normalize_video_record,
    read_json,
    run_command,
    safe_int,
    slugify,
    time_slug,
    now_iso,
    write_json,
)

YT_DLP = shutil.which("yt-dlp") or "yt-dlp"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local no-auth YouTube channel baselines for outlier scoring.")
    parser.add_argument("--channels-file", default=str(WATCHLISTS_DIR / "channels.yaml"))
    parser.add_argument("--from-search", help="Search bundle json path, defaults to latest search bundle")
    parser.add_argument("--include-search-channels", action="store_true", help="Also baseline channel URLs seen in latest search data")
    parser.add_argument("--limit-per-channel", type=int, default=30)
    parser.add_argument("--command-timeout-sec", type=float, default=20.0)
    parser.add_argument("--continue-on-error", action="store_true", default=True)
    return parser.parse_args()


def load_channels(args: argparse.Namespace) -> list[dict[str, Any]]:
    channels: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(name: str | None, url: str | None, source: str, layer: str | None = None, tags: list[str] | None = None) -> None:
        if not url:
            return
        key = url.rstrip("/").lower()
        if key in seen:
            return
        seen.add(key)
        channels.append({
            "name": name or url,
            "url": url,
            "source": source,
            "layer": layer,
            "tags": tags or [],
        })

    for item in load_channel_watchlist(args.channels_file):
        add(item.get("name"), item.get("url"), source="watchlist", layer=item.get("layer"), tags=item.get("tags") or [])

    if args.include_search_channels:
        bundle_path = latest_search_bundle(args.from_search)
        if bundle_path:
            bundle = read_json(bundle_path)
            for row in bundle.get("videos") or []:
                add(row.get("channel_name"), row.get("channel_url"), source="search", layer="search_result", tags=[])

    return channels


def channel_videos_url(channel_url: str) -> str:
    base = channel_url.rstrip("/")
    if any(base.endswith(f"/{tab}") for tab in ("videos", "shorts", "streams", "playlists")):
        return base
    if "youtube.com/" in base and any(marker in base for marker in ("/channel/", "/@", "/c/", "/user/")):
        return f"{base}/videos"
    return base


def fetch_channel_video_urls(channel_url: str, limit: int, timeout_sec: float) -> list[str]:
    result = run_command([
        YT_DLP,
        "--flat-playlist",
        "--playlist-end",
        str(limit),
        "--dump-single-json",
        channel_videos_url(channel_url),
    ], timeout_sec=timeout_sec)
    payload = json.loads(result.stdout)
    return [f"https://www.youtube.com/watch?v={item['id']}" for item in (payload.get("entries") or []) if item.get("id")]


def fetch_metadata_batch(urls: list[str], timeout_sec: float) -> list[dict[str, Any]]:
    if not urls:
        return []
    result = run_command([YT_DLP, "--dump-json", "--skip-download", *urls], timeout_sec=timeout_sec)
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def percentile(values: list[int], pct: float) -> float | None:
    cleaned = sorted(value for value in values if value >= 0)
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return float(cleaned[0])
    rank = (len(cleaned) - 1) * pct
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return float(cleaned[lo])
    weight = rank - lo
    return cleaned[lo] * (1 - weight) + cleaned[hi] * weight


def build_baseline(channel: dict[str, Any], raw_rows: list[dict[str, Any]], collected_at: str) -> dict[str, Any]:
    videos = [normalize_video_record(row, source="channel_baseline", query=channel.get("name"), collected_at=collected_at, source_provider="yt_dlp_channel") for row in raw_rows]
    views = [safe_int(row.get("views")) for row in videos if safe_int(row.get("views")) > 0]
    comments = [safe_int(row.get("comments_count")) for row in videos if safe_int(row.get("comments_count")) >= 0]
    median_views = float(median(views)) if views else None
    avg_views = round(sum(views) / len(views), 2) if views else None
    median_comments = float(median(comments)) if comments else None
    p75_views = percentile(views, 0.75)
    p90_views = percentile(views, 0.90)
    return {
        "collected_at": collected_at,
        "channel_name": channel.get("name"),
        "channel_url": channel.get("url"),
        "source": channel.get("source"),
        "layer": channel.get("layer"),
        "tags": channel.get("tags") or [],
        "sample_size": len(videos),
        "usable_view_samples": len(views),
        "median_views": median_views,
        "average_views": avg_views,
        "p75_views": p75_views,
        "p90_views": p90_views,
        "median_comments": median_comments,
        "latest_videos": [
            {
                "video_id": row.get("video_id"),
                "title": row.get("title"),
                "video_url": row.get("video_url"),
                "published_at": row.get("published_at"),
                "views": row.get("views"),
                "comments_count": row.get("comments_count"),
                "thumbnail_url": row.get("thumbnail_url"),
                "duration": row.get("duration"),
            }
            for row in videos[:50]
        ],
        "status": "ok" if views else "no_view_samples",
    }


def main() -> None:
    args = parse_args()
    CHANNEL_BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    collected_at = now_iso()
    run_id = time_slug()
    channels = load_channels(args)
    index: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for idx, channel in enumerate(channels, start=1):
        name = channel.get("name") or channel.get("url") or "unknown"
        print(f"[yt-baseline] {idx}/{len(channels)} {name} start", file=sys.stderr, flush=True)
        try:
            urls = fetch_channel_video_urls(channel["url"], args.limit_per_channel, args.command_timeout_sec)
            raw_rows = fetch_metadata_batch(urls, args.command_timeout_sec)
            baseline = build_baseline(channel, raw_rows, collected_at)
            slug = slugify(name)
            out_path = CHANNEL_BASELINES_DIR / f"{slug}.json"
            write_json(out_path, baseline)
            index.append({
                "channel_name": baseline.get("channel_name"),
                "channel_url": baseline.get("channel_url"),
                "path": str(out_path),
                "sample_size": baseline.get("sample_size"),
                "median_views": baseline.get("median_views"),
                "status": baseline.get("status"),
            })
            print(f"[yt-baseline] {name} status={baseline.get('status')} sample={baseline.get('sample_size')}", file=sys.stderr, flush=True)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError, OSError) as exc:
            error = {"channel_name": name, "channel_url": channel.get("url"), "error": str(exc)[-500:], "status": "error"}
            errors.append(error)
            print(f"[yt-baseline] {name} status=error", file=sys.stderr, flush=True)
            if not args.continue_on_error:
                raise

    summary = {
        "run_id": run_id,
        "collected_at": collected_at,
        "channels_total": len(channels),
        "channels_ok": sum(1 for item in index if item.get("status") == "ok"),
        "channels_error": len(errors),
        "limit_per_channel": args.limit_per_channel,
        "index": index,
        "errors": errors,
        "notes": [
            "No YouTube API key or account is used; data comes from public yt-dlp metadata.",
            "Baseline median is computed from recent channel videos and is used for outlier multipliers.",
        ],
    }
    index_path = CHANNEL_BASELINES_DIR / "index.json"
    run_path = CHANNEL_BASELINES_DIR / f"run-{run_id}.json"
    write_json(index_path, summary)
    write_json(run_path, summary)
    print(json.dumps({"index_path": str(index_path), "run_path": str(run_path), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
