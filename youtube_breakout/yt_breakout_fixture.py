#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .common import public_path_label, safe_child_path, write_json, write_jsonl, write_text
from .yt_breakout_analyzer import AnalysisOptions, analyze_project


TOOL_ROOT = Path(__file__).resolve().parent
DEFAULT_PROJECT_ROOT = Path(os.environ.get("YOUTUBE_INTEL_PROJECT_ROOT", str(TOOL_ROOT))).resolve()
FIXTURE_AT = "2026-07-16T00:00:00+00:00"


def video(
    *,
    video_id: str,
    title: str,
    channel_name: str,
    channel_url: str,
    views: int,
    comments_count: int,
    published_at: str,
    duration: str,
    query: str,
    description: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "query": query,
        "source": "fixture_search",
        "source_provider": "fixture",
        "collected_at": FIXTURE_AT,
        "title": title,
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "video_id": video_id,
        "channel_name": channel_name,
        "channel_url": channel_url,
        "published_at": published_at,
        "duration": duration,
        "views": views,
        "comments_count": comments_count,
        "likes": 0,
        "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        "description_snippet": description,
        "tags": tags or [],
    }


def baseline(channel_name: str, channel_url: str, median_views: int, sample_size: int, videos: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "collected_at": FIXTURE_AT,
        "channel_name": channel_name,
        "channel_url": channel_url,
        "source": "fixture",
        "layer": "direct",
        "tags": [],
        "sample_size": sample_size,
        "usable_view_samples": sample_size,
        "median_views": float(median_views),
        "average_views": float(median_views),
        "p75_views": float(median_views * 1.25),
        "p90_views": float(median_views * 1.5),
        "median_comments": max(float(median_views // 80), 1.0),
        "latest_videos": [
            {
                "video_id": row["video_id"],
                "title": row["title"],
                "video_url": row["video_url"],
                "published_at": row["published_at"],
                "views": row["views"],
                "comments_count": row["comments_count"],
                "thumbnail_url": row["thumbnail_url"],
                "duration": row["duration"],
            }
            for row in videos
        ],
        "status": "ok",
    }


def write_comments(project_root: Path, row: dict[str, Any], comments: list[str]) -> None:
    out_dir = safe_child_path(project_root / "data" / "comments", row["video_id"], field="video_id")
    rows = [
        {
            "video_id": row["video_id"],
            "comment_id": f"{row['video_id']}-{index}",
            "thread_id": f"{row['video_id']}-{index}",
            "parent_comment_id": None,
            "is_reply": False,
            "author": "fixture",
            "text": text,
            "likes": 10 - index,
            "published_at": FIXTURE_AT,
            "reply_count": 0,
            "sort_mode": "top",
            "collected_at": FIXTURE_AT,
        }
        for index, text in enumerate(comments, start=1)
    ]
    write_jsonl(out_dir / "latest.jsonl", rows)
    write_json(out_dir / "latest.meta.json", {
        "fetched_at": FIXTURE_AT,
        "collected_at": FIXTURE_AT,
        "video_id": row["video_id"],
        "video_url": row["video_url"],
        "title": row["title"],
        "channel_name": row["channel_name"],
        "channel_url": row["channel_url"],
        "comments_count": len(rows),
        "thread_roots_count": len(rows),
        "reply_rows_count": 0,
        "sort_modes": ["top"],
        "status": "ok" if rows else "empty",
        "errors": {},
        "source": "fixture_comments",
    })


def write_fixture_project(project_root: Path) -> dict[str, Any]:
    for rel in [
        "watchlists",
        "data/search/2026-07-16",
        "data/channel_baselines",
        "data/comments",
        "data/thumbnails",
        "data/thumbnail_vision",
        "result",
    ]:
        (project_root / rel).mkdir(parents=True, exist_ok=True)

    write_text(project_root / "watchlists" / "topics.yaml", "\n".join([
        "topics:",
        "  - silent walking rain",
        "  - city walk no talking",
        "  - ai automation demo",
        "  - n8n workflow automation",
        "",
    ]))
    write_text(project_root / "watchlists" / "channels.yaml", "\n".join([
        "direct:",
        "  - name: Rain Walks Micro",
        "    url: https://www.youtube.com/@rainwalksmicro",
        "    enabled: true",
        "    tags: [walking]",
        "  - name: Quiet Seoul Walks",
        "    url: https://www.youtube.com/@quietseoulwalks",
        "    enabled: true",
        "    tags: [walking]",
        "  - name: City Lens",
        "    url: https://www.youtube.com/@citylens",
        "    enabled: true",
        "    tags: [walking]",
        "  - name: New Walker",
        "    url: https://www.youtube.com/@newwalker",
        "    enabled: true",
        "    tags: [walking]",
        "adjacent:",
        "  - name: Automate Small",
        "    url: https://www.youtube.com/@automatesmall",
        "    enabled: true",
        "    tags: [ai-automation]",
        "  - name: Ops Agent Lab",
        "    url: https://www.youtube.com/@opsagentlab",
        "    enabled: true",
        "    tags: [ai-automation]",
        "",
    ]))

    walking = [
        video(
            video_id="walk_tokyo_rain",
            title="Tokyo Rain Night Walk 4K - Shinjuku Backstreets - No Talking",
            channel_name="Rain Walks Micro",
            channel_url="https://www.youtube.com/@rainwalksmicro",
            views=12000,
            comments_count=180,
            published_at="2026-07-10T00:00:00+00:00",
            duration="1:04:00",
            query="silent walking rain",
            description="A silent rain walk through ordinary Shinjuku backstreets with ambient sound.",
            tags=["walking", "rain", "tokyo"],
        ),
        video(
            video_id="walk_tokyo_counter",
            title="Tokyo Rain Walking Tour 4K - Quiet Afternoon",
            channel_name="Rain Walks Micro",
            channel_url="https://www.youtube.com/@rainwalksmicro",
            views=600,
            comments_count=8,
            published_at="2026-07-08T00:00:00+00:00",
            duration="42:00",
            query="silent walking rain",
            description="Rain walking tour in Tokyo.",
            tags=["walking", "rain", "tokyo"],
        ),
        video(
            video_id="walk_seoul_snow",
            title="Seoul Snow Morning Walk 4K - Silent Residential Streets",
            channel_name="Quiet Seoul Walks",
            channel_url="https://www.youtube.com/@quietseoulwalks",
            views=8000,
            comments_count=90,
            published_at="2026-07-09T00:00:00+00:00",
            duration="55:00",
            query="city walk no talking",
            description="Silent Seoul snow walk through ordinary residential streets.",
            tags=["walking", "snow", "seoul"],
        ),
        video(
            video_id="walk_paris_night",
            title="Paris Night Walk 4K HDR - Rain Reflections, No Commentary",
            channel_name="City Lens",
            channel_url="https://www.youtube.com/@citylens",
            views=650000,
            comments_count=2400,
            published_at="2026-07-11T00:00:00+00:00",
            duration="1:20:00",
            query="city walk no talking",
            description="Night walk in Paris with wet reflections and no commentary.",
            tags=["walking", "rain", "paris"],
        ),
        video(
            video_id="walk_new_insufficient",
            title="Lisbon Rain Walk 4K - Quiet Ordinary Neighborhood",
            channel_name="New Walker",
            channel_url="https://www.youtube.com/@newwalker",
            views=5000,
            comments_count=70,
            published_at="2026-07-12T00:00:00+00:00",
            duration="38:00",
            query="silent walking rain",
            description="Rain walk in an ordinary Lisbon neighborhood.",
            tags=["walking", "rain", "lisbon"],
        ),
        video(
            video_id="walk_topic_base_a",
            title="Kyoto Day Walk 4K - No Talking",
            channel_name="Rain Walks Micro",
            channel_url="https://www.youtube.com/@rainwalksmicro",
            views=1000,
            comments_count=10,
            published_at="2026-07-06T00:00:00+00:00",
            duration="35:00",
            query="silent walking rain",
            description="Day walk with no talking.",
            tags=["walking", "kyoto"],
        ),
        video(
            video_id="walk_topic_base_b",
            title="Seoul Clear Day Walking Tour 4K",
            channel_name="Quiet Seoul Walks",
            channel_url="https://www.youtube.com/@quietseoulwalks",
            views=1200,
            comments_count=14,
            published_at="2026-07-04T00:00:00+00:00",
            duration="34:00",
            query="silent walking rain",
            description="Clear day walking tour.",
            tags=["walking", "seoul"],
        ),
        video(
            video_id="walk_topic_base_c",
            title="Paris Ordinary Neighborhood Walk 4K",
            channel_name="City Lens",
            channel_url="https://www.youtube.com/@citylens",
            views=90000,
            comments_count=300,
            published_at="2026-07-02T00:00:00+00:00",
            duration="45:00",
            query="silent walking rain",
            description="Ordinary neighborhood walk.",
            tags=["walking", "paris"],
        ),
    ]
    ai = [
        video(
            video_id="ai_n8n_invoice",
            title="I Built an n8n AI Agent for Invoices - Real Workflow Demo",
            channel_name="Automate Small",
            channel_url="https://www.youtube.com/@automatesmall",
            views=15000,
            comments_count=140,
            published_at="2026-07-10T00:00:00+00:00",
            duration="24:00",
            query="ai automation demo",
            description="Step by step n8n automation for invoice processing with saved hours.",
            tags=["ai", "automation", "n8n"],
        ),
        video(
            video_id="ai_ops_agent",
            title="Claude Agents for Ops Reporting - Production Case Study",
            channel_name="Ops Agent Lab",
            channel_url="https://www.youtube.com/@opsagentlab",
            views=22000,
            comments_count=160,
            published_at="2026-07-09T00:00:00+00:00",
            duration="31:00",
            query="n8n workflow automation",
            description="AI agent workflow for reporting dashboard and production ops.",
            tags=["ai", "agents", "ops"],
        ),
        video(
            video_id="ai_counter",
            title="n8n Automation Tutorial for Beginners",
            channel_name="Automate Small",
            channel_url="https://www.youtube.com/@automatesmall",
            views=1200,
            comments_count=12,
            published_at="2026-07-08T00:00:00+00:00",
            duration="18:00",
            query="ai automation demo",
            description="Beginner tutorial.",
            tags=["ai", "automation", "n8n"],
        ),
    ]
    all_videos = walking + ai
    write_json(project_root / "data" / "search" / "2026-07-16" / "search-20260716-000000.json", {
        "run_at": FIXTURE_AT,
        "queries": ["silent walking rain", "city walk no talking", "ai automation demo", "n8n workflow automation"],
        "query_runs": [],
        "watchlist_channel_runs": [],
        "videos_count": len(all_videos),
        "derived_channels_count": 6,
        "search_provider": "fixture",
        "fallback_providers": [],
        "notes": ["Deterministic local fixture; no network access."],
        "videos": all_videos,
        "derived_channels": [],
    })

    channel_groups: dict[str, list[dict[str, Any]]] = {}
    for row in all_videos:
        channel_groups.setdefault(row["channel_name"], []).append(row)
    baseline_specs = {
        "Rain Walks Micro": ("https://www.youtube.com/@rainwalksmicro", 500, 30),
        "Quiet Seoul Walks": ("https://www.youtube.com/@quietseoulwalks", 800, 24),
        "City Lens": ("https://www.youtube.com/@citylens", 100000, 40),
        "New Walker": ("https://www.youtube.com/@newwalker", 100, 2),
        "Automate Small": ("https://www.youtube.com/@automatesmall", 1000, 25),
        "Ops Agent Lab": ("https://www.youtube.com/@opsagentlab", 2000, 20),
    }
    index = []
    for channel_name, (channel_url, median_views, sample_size) in baseline_specs.items():
        payload = baseline(channel_name, channel_url, median_views, sample_size, channel_groups.get(channel_name, []))
        out_path = project_root / "data" / "channel_baselines" / f"{channel_name.lower().replace(' ', '-')}.json"
        write_json(out_path, payload)
        index.append({
            "channel_name": channel_name,
            "channel_url": channel_url,
            "path": public_path_label(out_path, root=project_root),
            "sample_size": sample_size,
            "median_views": median_views,
            "status": "ok",
        })
    write_json(project_root / "data" / "channel_baselines" / "index.json", {
        "run_id": "fixture",
        "collected_at": FIXTURE_AT,
        "channels_total": len(index),
        "channels_ok": len(index),
        "channels_error": 0,
        "limit_per_channel": 30,
        "index": index,
        "errors": [],
    })

    write_comments(project_root, walking[0], [
        "The rain sound is perfect for sleep and work background.",
        "I use this on the treadmill and it feels like virtual travel.",
        "Please share the route, these ordinary neighborhoods are better than tourist spots.",
    ])
    write_comments(project_root, walking[2], [
        "Snowy quiet streets make me miss Seoul.",
        "Great indoor walk for my walking pad.",
        "I like the real life residential route.",
    ])
    write_comments(project_root, walking[3], [
        "Rain reflections and no commentary are so relaxing.",
        "Planning my trip and this route helps.",
        "The night walk feels safe and real.",
    ])
    write_comments(project_root, ai[0], [
        "Trying this invoice workflow at work tomorrow.",
        "Thanks for showing the real n8n nodes and saved hours.",
        "What is the pricing for this setup?",
    ])
    write_comments(project_root, ai[1], [
        "This production case study makes agents less confusing.",
        "I will implement the reporting dashboard workflow.",
        "Good proof that this can be reliable in ops.",
    ])

    thumb_items = []
    vision_items = []
    for rank, row in enumerate([walking[0], walking[2], walking[3], ai[0], ai[1]], start=1):
        labels = ["high-contrast", "saturated/color-pop"]
        if row["video_id"].startswith("walk"):
            labels.append("dark")
            visuals = ["wet street reflections", "deep street perspective", "no text", "single person"]
            hook = "rain night no-text depth"
        else:
            labels.append("dense/text-or-detail-heavy")
            visuals = ["workflow UI", "dashboard", "metric result"]
            hook = "tool UI proof metric"
        thumb_items.append({
            "rank": rank,
            "video_id": row["video_id"],
            "title": row["title"],
            "channel_name": row["channel_name"],
            "video_url": row["video_url"],
            "thumbnail_url": row["thumbnail_url"],
            "status": "fixture",
            "visual_metrics": {
                "status": "fixture",
                "labels": labels,
                "brightness": 80,
                "contrast": 70,
                "saturation": 130,
                "edge_density_proxy": 35,
                "colorfulness": 80,
            },
        })
        vision_items.append({
            "rank": rank,
            "video_id": row["video_id"],
            "title": row["title"],
            "hook_type": hook,
            "visible_text": [],
            "main_visuals": visuals,
            "why_it_may_work": "fixture semantic visual labels for local deterministic tests",
            "image_path": None,
        })
    write_json(project_root / "data" / "thumbnails" / "latest.json", {
        "generated_at": FIXTURE_AT,
        "items": thumb_items,
    })
    write_json(project_root / "data" / "thumbnail_vision" / "latest.json", {
        "generated_at": FIXTURE_AT,
        "source": "fixture_provider_neutral_manifest",
        "items": vision_items,
    })
    return {"videos": len(all_videos), "project_root": "."}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write deterministic breakout fixture data and run the analyzer without network access.")
    parser.add_argument("--project-root", default=str(DEFAULT_PROJECT_ROOT))
    parser.add_argument("--niche", choices=["walking", "ai-automation"], default="walking")
    parser.add_argument("--mode", choices=["metadata-only", "metadata+comments", "metadata+visual", "full-public"], default="full-public")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refresh known fixture files; saved run copies use the next free suffix. No broad deletion is performed.",
    )
    return parser


def next_fixture_run_id(project_root: Path, niche: str) -> str:
    base = f"fixture-{niche}"
    runs_root = project_root / "result" / "breakout-runs"
    candidate = base
    suffix = 2
    while True:
        run_dir = safe_child_path(runs_root, candidate, field="run_id")
        if not run_dir.exists() and not run_dir.is_symlink():
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def main() -> None:
    args = build_parser().parse_args()
    project_root = Path(args.project_root).resolve()
    fixture_marker = project_root / "data" / "search" / "2026-07-16" / "search-20260716-000000.json"
    if fixture_marker.exists() and not args.force:
        raise SystemExit(f"fixture already exists; rerun with --force: {fixture_marker}")
    project_root.mkdir(parents=True, exist_ok=True)
    fixture = write_fixture_project(project_root)
    config_path = TOOL_ROOT / "configs" / "niches" / f"{args.niche}.yaml"
    analysis = analyze_project(AnalysisOptions(
        project_root=project_root,
        niche_config=config_path,
        limit_per_channel=30,
        top_outliers=25,
        mode=args.mode,
        analysis_at=FIXTURE_AT,
        run_id=next_fixture_run_id(project_root, args.niche),
    ))
    print(json.dumps({
        "fixture": fixture,
        "niche": args.niche,
        "outputs": analysis["outputs"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
