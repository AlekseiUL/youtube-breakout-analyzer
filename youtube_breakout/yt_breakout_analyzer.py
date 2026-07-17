#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from .common import (
    load_channel_watchlist,
    load_yaml,
    max_optional_int,
    now_iso,
    optional_int,
    public_path_label as common_public_path_label,
    read_json,
    read_jsonl,
    safe_int,
    safe_child_path,
    time_slug,
    validate_path_slug,
    write_json,
    write_text,
)


TOOL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_ROOT = Path(os.environ.get("YOUTUBE_INTEL_PROJECT_ROOT", str(TOOL_ROOT))).resolve()
FRAME_SAMPLE_POINTS = ["0-10s", "30s", "5%", "25%", "50%", "75%", "95%"]
MODE_CHOICES = ["metadata-only", "metadata+comments", "metadata+visual", "full-public"]
CAUSALITY_WARNING = "association, not proven cause"


@dataclass
class AnalysisOptions:
    project_root: Path
    niche_config: Path
    channels_file: Path | None = None
    topics_file: Path | None = None
    from_search: Path | None = None
    limit_per_channel: int = 30
    top_outliers: int = 25
    mode: str = "full-public"
    analysis_at: str | None = None
    out_dir: Path | None = None
    run_id: str | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze public YouTube breakout candidates from local artifacts.")
    parser.add_argument("--project-root", default=str(DEFAULT_PROJECT_ROOT))
    parser.add_argument("--niche-config", required=True, help="Niche taxonomy YAML. Relative paths resolve against project root then tool root.")
    parser.add_argument("--channels-file", help="Channel watchlist YAML. Defaults to <project-root>/watchlists/channels.yaml")
    parser.add_argument("--topics-file", help="Topic/query YAML. Defaults to <project-root>/watchlists/topics.yaml")
    parser.add_argument("--from-search", help="Search bundle JSON. Defaults to latest local search bundle.")
    parser.add_argument("--limit-per-channel", type=int, default=30)
    parser.add_argument("--top-outliers", type=int, default=25)
    parser.add_argument("--mode", choices=MODE_CHOICES, default="full-public")
    parser.add_argument("--analysis-at", help="ISO timestamp used for deterministic video-age calculations.")
    parser.add_argument("--out-dir", help="Output directory. Defaults to <project-root>/result")
    parser.add_argument("--run-id", help="Stable run id for deterministic fixture/test runs.")
    return parser


def public_path_label(path: str | Path | None, project_root: Path) -> str | None:
    """Return a release-safe path label without serializing a user's home directory."""
    return common_public_path_label(path, root=project_root)


def resolve_existing_path(project_root: Path, raw: str | Path | None, default: Path | None = None) -> Path | None:
    if raw is None:
        return default
    path = Path(raw)
    candidates = [path]
    if not path.is_absolute():
        candidates = [Path.cwd() / path, project_root / path, TOOL_ROOT / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return (project_root / path).resolve() if not path.is_absolute() else path


def load_niche_config(project_root: Path, raw_path: str | Path) -> dict[str, Any]:
    path = resolve_existing_path(project_root, raw_path)
    if not path or not path.exists():
        raise SystemExit(f"niche config not found: {raw_path}")
    config = load_yaml(path)
    if not isinstance(config, dict) or not config.get("niche"):
        raise SystemExit(f"niche config must include `niche`: {path}")
    config["_path"] = str(path)
    config.setdefault("thresholds", {"strong": 5.0, "breakout": 10.0, "extreme": 20.0})
    config.setdefault("baseline", {"min_channel_samples": 5, "min_topic_samples": 3})
    config.setdefault("small_channel", {"median_views_max": 50000})
    return config


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        if "T" not in text and len(text) == 10:
            text = text + "T00:00:00+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def duration_seconds(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    parts = text.split(":")
    if not all(part.isdigit() for part in parts):
        return None
    total = 0
    for part in parts:
        total = total * 60 + int(part)
    return total


def norm_key(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).strip().rstrip("/").lower()


def clean_join(values: list[Any]) -> str:
    return " ".join(str(value or "") for value in values).lower()


def contains_keyword(text: str, keyword: str) -> bool:
    normalized = keyword.strip().lower()
    if not normalized:
        return False
    if normalized[0].isalnum() and normalized[-1].isalnum():
        return re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", text) is not None
    return normalized in text


def latest_search_bundle(project_root: Path, explicit: Path | None = None) -> Path | None:
    if explicit:
        return explicit
    search_dir = project_root / "data" / "search"
    matches = sorted(
        path for path in search_dir.glob("**/search-*.json")
        if not path.name.endswith(".channels.json") and not path.name.endswith(".videos.json")
    )
    return matches[-1] if matches else None


def load_topics(path: Path) -> list[str]:
    if not path.exists():
        return []
    payload = load_yaml(path)
    return [str(item).strip() for item in (payload.get("topics") or []) if str(item).strip()]


def load_baselines(project_root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    baselines_dir = project_root / "data" / "channel_baselines"
    by_key: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for path in sorted(baselines_dir.glob("*.json")):
        if path.name.startswith("run-") or path.name == "index.json":
            continue
        try:
            payload = read_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        payload["_path"] = public_path_label(path, project_root)
        rows.append(payload)
        for key in [payload.get("channel_url"), payload.get("channel_name")]:
            normalized = norm_key(key)
            if normalized:
                by_key[normalized] = payload
    return by_key, rows


def find_baseline(item: dict[str, Any], baselines_by_key: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for key in [item.get("channel_url"), item.get("channel_name")]:
        normalized = norm_key(key)
        if normalized and normalized in baselines_by_key:
            return baselines_by_key[normalized]
    return None


def merge_video(target: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
    key = row.get("video_id") or row.get("video_url")
    if not key:
        return
    item = target.setdefault(str(key), {
        "video_id": row.get("video_id"),
        "video_url": row.get("video_url"),
        "title": None,
        "channel_name": None,
        "channel_url": None,
        "published_at": None,
        "duration": None,
        "views": None,
        "comments_count": None,
        "description_snippet": "",
        "thumbnail_url": None,
        "queries": set(),
        "watchlist_tags": set(),
        "sources": set(),
        "source_providers": set(),
        "collected_at": None,
    })
    for field in ["title", "video_url", "video_id", "channel_name", "channel_url", "published_at", "duration", "description_snippet", "thumbnail_url", "collected_at"]:
        if not item.get(field) and row.get(field):
            item[field] = row.get(field)
    item["views"] = max_optional_int(item.get("views"), row.get("views"))
    item["comments_count"] = max_optional_int(item.get("comments_count"), row.get("comments_count"))
    if row.get("query"):
        item["queries"].add(str(row.get("query")))
    for query in row.get("queries") or []:
        item["queries"].add(str(query))
    for tag in row.get("watchlist_tags") or row.get("tags") or []:
        item["watchlist_tags"].add(str(tag))
    if row.get("source"):
        item["sources"].add(str(row.get("source")))
    if row.get("source_provider"):
        item["source_providers"].add(str(row.get("source_provider")))


def load_candidate_videos(
    project_root: Path,
    *,
    search_path: Path | None,
    baseline_rows: list[dict[str, Any]],
    limit_per_channel: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    videos: dict[str, dict[str, Any]] = {}
    bundle_path = latest_search_bundle(project_root, search_path)
    bundle = None
    if bundle_path and bundle_path.exists():
        bundle = read_json(bundle_path)
        for row in bundle.get("videos") or []:
            merge_video(videos, row)

    for baseline in baseline_rows:
        channel_name = baseline.get("channel_name")
        channel_url = baseline.get("channel_url")
        for row in (baseline.get("latest_videos") or [])[:limit_per_channel]:
            enriched = dict(row)
            enriched.setdefault("channel_name", channel_name)
            enriched.setdefault("channel_url", channel_url)
            enriched.setdefault("source", "channel_baseline_latest_video")
            enriched.setdefault("query", channel_name)
            merge_video(videos, enriched)

    rows: list[dict[str, Any]] = []
    for item in videos.values():
        item["queries"] = sorted(item["queries"])
        item["watchlist_tags"] = sorted(item["watchlist_tags"])
        item["sources"] = sorted(item["sources"])
        item["source_providers"] = sorted(item["source_providers"])
        rows.append(item)
    rows.sort(key=lambda item: (safe_int(item.get("views")), item.get("title") or ""), reverse=True)
    return rows, {
        "search_bundle_path": public_path_label(bundle_path, project_root),
        "search_bundle_videos": len(bundle.get("videos") or []) if bundle else 0,
        "candidate_videos": len(rows),
    }


def outlier_tier(multiplier: float | None, thresholds: dict[str, Any]) -> str | None:
    if multiplier is None:
        return None
    strong = float(thresholds.get("strong", 5.0))
    breakout = float(thresholds.get("breakout", 10.0))
    extreme = float(thresholds.get("extreme", 20.0))
    if multiplier >= extreme:
        return f"{extreme:g}x+ extreme"
    if multiplier >= breakout:
        return f"{breakout:g}x+ breakout"
    if multiplier >= strong:
        return f"{strong:g}x+ strong"
    return "below strong threshold"


def video_age_days(published_at: str | None, analysis_at: datetime) -> float | None:
    published = parse_dt(published_at)
    if not published:
        return None
    seconds = max((analysis_at - published).total_seconds(), 0)
    return max(seconds / 86400, 1 / 24)


def enrich_channel_signals(
    videos: list[dict[str, Any]],
    baselines_by_key: dict[str, dict[str, Any]],
    config: dict[str, Any],
    analysis_at: datetime,
) -> None:
    thresholds = config.get("thresholds") or {}
    min_samples = int((config.get("baseline") or {}).get("min_channel_samples") or 5)
    for item in videos:
        baseline = find_baseline(item, baselines_by_key)
        views = optional_int(item.get("views"))
        comments = optional_int(item.get("comments_count"))
        age_days = video_age_days(item.get("published_at"), analysis_at)
        views_per_day = round(views / age_days, 2) if views is not None and age_days else None
        comments_per_day = round(comments / age_days, 2) if comments is not None and age_days else None
        comment_rate = round((comments / views) * 1000, 3) if comments is not None and views and views > 0 else None

        raw_sample_size = safe_int(baseline.get("sample_size")) if baseline else 0
        sample_size = safe_int(baseline.get("usable_view_samples"), default=raw_sample_size) if baseline else 0
        median_views = number(baseline.get("median_views")) if baseline else None
        median_comments = number(baseline.get("median_comments")) if baseline else None
        baseline_status = "OK"
        if not baseline:
            baseline_status = "NO_CHANNEL_BASELINE"
        elif sample_size < min_samples or not median_views or median_views <= 0:
            baseline_status = "INSUFFICIENT_CHANNEL_BASELINE"

        multiplier = None
        if baseline_status == "OK" and median_views and median_views > 0 and views is not None and views > 0:
            multiplier = round(views / median_views, 2)
        comment_multiplier = None
        if baseline_status == "OK" and median_comments and median_comments > 0 and comments is not None and comments > 0:
            comment_multiplier = round(comments / median_comments, 2)

        item.update({
            "video_age_days": round(age_days, 3) if age_days is not None else None,
            "views_per_day": views_per_day,
            "comments_per_day": comments_per_day,
            "comment_rate_per_1000_views": comment_rate,
            "channel_recent_median_views": median_views,
            "channel_median_comments": median_comments,
            "channel_outlier_multiplier": multiplier,
            "channel_outlier_tier": outlier_tier(multiplier, thresholds),
            "comment_multiplier": comment_multiplier,
            "channel_baseline_status": baseline_status,
            "channel_baseline_sample_size": sample_size,
            "channel_baseline": {
                "matched": bool(baseline),
                "status": baseline_status,
                "sample_size": raw_sample_size,
                "usable_view_samples": sample_size,
                "median_views": median_views,
                "median_comments": median_comments,
                "channel_name": baseline.get("channel_name") if baseline else None,
                "channel_url": baseline.get("channel_url") if baseline else None,
                "source_path": baseline.get("_path") if baseline else None,
            },
        })


def topic_keys(item: dict[str, Any], topics: list[str]) -> list[str]:
    keys: set[str] = set()
    channel_name = str(item.get("channel_name") or "").strip().lower()
    text = clean_join([
        item.get("title"),
        item.get("description_snippet"),
        " ".join(item.get("watchlist_tags") or []),
    ])
    for query in item.get("queries") or []:
        key = str(query).strip().lower()
        if key and key != channel_name:
            keys.add(key)
    for topic in topics:
        key = topic.strip().lower()
        if key and key in text:
            keys.add(key)
    for tag in item.get("watchlist_tags") or []:
        key = str(tag).strip().lower()
        if key:
            keys.add(f"tag:{key}")
    return sorted(keys)


def enrich_topic_signals(videos: list[dict[str, Any]], topics: list[str], config: dict[str, Any]) -> None:
    min_samples = int((config.get("baseline") or {}).get("min_topic_samples") or 3)
    buckets: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for item in videos:
        item["topic_keys"] = topic_keys(item, topics)
        vpd = item.get("views_per_day")
        if not vpd:
            continue
        video_key = str(item.get("video_id") or item.get("video_url") or item.get("title"))
        for key in item["topic_keys"]:
            buckets[key].append((video_key, float(vpd)))

    for item in videos:
        video_key = str(item.get("video_id") or item.get("video_url") or item.get("title"))
        current_vpd = item.get("views_per_day")
        best: dict[str, Any] | None = None
        for key in item.get("topic_keys") or []:
            values = [value for candidate_key, value in buckets.get(key, []) if candidate_key != video_key]
            if len(values) < min_samples or not current_vpd:
                candidate = {"topic_key": key, "status": "INSUFFICIENT_TOPIC_BASELINE", "sample_size": len(values)}
            else:
                topic_median = float(median(values))
                candidate = {
                    "topic_key": key,
                    "status": "OK",
                    "sample_size": len(values),
                    "topic_median_views_per_day": round(topic_median, 2),
                    "topic_ratio": round(float(current_vpd) / topic_median, 2) if topic_median > 0 else None,
                }
            if best is None or (candidate.get("topic_ratio") or 0) > (best.get("topic_ratio") or 0):
                best = candidate
        best = best or {"status": "NO_TOPIC", "sample_size": 0, "topic_key": None}
        item.update({
            "topic_baseline_status": best.get("status"),
            "topic_median_views_per_day": best.get("topic_median_views_per_day"),
            "topic_ratio": best.get("topic_ratio"),
            "topic_baseline_sample_size": best.get("sample_size"),
            "topic_baseline": best,
        })


def mode_layers(mode: str) -> dict[str, bool]:
    return {
        "comments": mode in {"metadata+comments", "full-public"},
        "visual": mode in {"metadata+visual", "full-public"},
        "transcripts": mode == "full-public",
    }


def load_comment_artifacts(project_root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    comments_dir = project_root / "data" / "comments"
    for meta_path in sorted(comments_dir.glob("*/latest.meta.json")):
        try:
            meta = read_json(meta_path)
            rows = read_jsonl(meta_path.parent / "latest.jsonl")
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        video_id = meta.get("video_id") or meta_path.parent.name
        result[str(video_id)] = {"meta": meta, "rows": rows}
    return result


def load_transcript_artifacts(project_root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted((project_root / "data" / "transcripts").glob("*/latest.json")):
        try:
            payload = read_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        video_id = payload.get("video_id") or path.parent.name
        result[str(video_id)] = payload
    return result


def load_thumbnail_artifacts(project_root: Path) -> dict[str, dict[str, Any]]:
    latest = project_root / "data" / "thumbnails" / "latest.json"
    if not latest.exists():
        return {}
    try:
        payload = read_json(latest)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in payload.get("items") or []:
        if row.get("video_id"):
            result[str(row["video_id"])] = row
    return result


def load_thumbnail_vision_artifacts(project_root: Path) -> dict[str, dict[str, Any]]:
    latest = project_root / "data" / "thumbnail_vision" / "latest.json"
    if not latest.exists():
        return {}
    try:
        payload = read_json(latest)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in payload.get("items") or []:
        if row.get("video_id"):
            result[str(row["video_id"])] = row
    return result


def pattern_match(haystack: str, patterns: list[Any]) -> bool:
    return any(str(pattern).lower() in haystack for pattern in patterns if str(pattern).strip())


def add_feature(features: dict[tuple[str, str], dict[str, Any]], source: str, group: str, label: str, evidence: str) -> None:
    key = (f"{group}:{label}", source)
    item = features.setdefault(key, {
        "id": f"{group}:{label}",
        "pattern": f"{group}: {label}",
        "group": group,
        "label": label,
        "source": source,
        "evidence": [],
    })
    if evidence and evidence not in item["evidence"]:
        item["evidence"].append(evidence[:220])


def extract_rule_features(
    features: dict[tuple[str, str], dict[str, Any]],
    *,
    source: str,
    rules: dict[str, Any],
    haystack: str,
    evidence: str,
) -> None:
    for group, labels in (rules or {}).items():
        if not isinstance(labels, dict):
            continue
        for label, patterns in labels.items():
            if pattern_match(haystack, patterns or []):
                add_feature(features, source, str(group), str(label), evidence)


def add_duration_feature(
    features: dict[tuple[str, str], dict[str, Any]],
    duration: Any,
    config: dict[str, Any],
) -> None:
    seconds = duration_seconds(duration)
    if seconds is None:
        return
    for label, bounds in (config.get("duration_buckets") or {}).items():
        if not isinstance(bounds, dict):
            continue
        min_seconds = int(bounds.get("min_seconds") or 0)
        max_seconds = bounds.get("max_seconds")
        if seconds >= min_seconds and (max_seconds is None or seconds <= int(max_seconds)):
            add_feature(features, "metadata", "duration", str(label), f"{seconds}s")
            return


def extract_features_for_video(
    item: dict[str, Any],
    config: dict[str, Any],
    *,
    layers: dict[str, bool],
    comments: dict[str, dict[str, Any]],
    thumbnails: dict[str, dict[str, Any]],
    thumbnail_vision: dict[str, dict[str, Any]],
    transcripts: dict[str, dict[str, Any]],
) -> None:
    video_id = str(item.get("video_id") or "")
    features: dict[tuple[str, str], dict[str, Any]] = {}
    title_text = clean_join([
        item.get("title"),
        item.get("description_snippet"),
        " ".join(item.get("queries") or []),
        " ".join(item.get("watchlist_tags") or []),
    ])
    extract_rule_features(
        features,
        source="metadata",
        rules=config.get("metadata_features") or {},
        haystack=title_text,
        evidence=item.get("title") or "",
    )
    add_duration_feature(features, item.get("duration"), config)

    coverage = {
        "metadata": "OK",
        "comments": "NOT_REQUESTED",
        "visual": "NOT_REQUESTED",
        "transcripts": "NOT_REQUESTED",
        "frame_sampling": "NOT_REQUESTED",
        "audio": "NOT_AVAILABLE_WITHOUT_OPTIONAL_ANALYSIS",
    }

    if layers["comments"]:
        comment_payload = comments.get(video_id)
        if comment_payload and comment_payload.get("rows"):
            coverage["comments"] = "OK"
            comment_text = clean_join([row.get("text") for row in comment_payload.get("rows") or []])
            extract_rule_features(
                features,
                source="comments",
                rules=config.get("comment_features") or {},
                haystack=comment_text,
                evidence=" | ".join((row.get("text") or "")[:120] for row in (comment_payload.get("rows") or [])[:2]),
            )
        elif comment_payload:
            coverage["comments"] = f"NO_COMMENT_ROWS:{(comment_payload.get('meta') or {}).get('status') or 'empty'}"
        else:
            coverage["comments"] = "MISSING_COMMENTS_ARTIFACTS"

    if layers["visual"]:
        visual_text_parts: list[str] = []
        thumb = thumbnails.get(video_id)
        vision = thumbnail_vision.get(video_id)
        visual_statuses: list[str] = []
        if thumb:
            metrics = thumb.get("visual_metrics") or {}
            thumb_status = str(thumb.get("status") or "").lower()
            metrics_status = str(metrics.get("status") or "").lower()
            if thumb_status == "ok" and metrics_status == "ok":
                visual_text_parts.extend(str(label) for label in metrics.get("labels") or [])
            else:
                visual_statuses.append(str(metrics.get("status") or thumb.get("status") or "unavailable"))
        if vision:
            vision_status = str(vision.get("status") or "ok").lower()
            if vision_status == "ok":
                visual_text_parts.extend(str(value) for value in vision.get("main_visuals") or [])
                visual_text_parts.extend(str(value) for value in vision.get("visible_text") or [])
                visual_text_parts.append(str(vision.get("hook_type") or ""))
                visual_text_parts.append(str(vision.get("why_it_may_work") or ""))
            else:
                visual_statuses.append(str(vision.get("status") or "unavailable"))
        if visual_text_parts:
            coverage["visual"] = "OK"
            extract_rule_features(
                features,
                source="visual",
                rules=config.get("visual_features") or {},
                haystack=clean_join(visual_text_parts),
                evidence="; ".join(visual_text_parts[:8]),
            )
        elif thumb or vision:
            status_label = ",".join(sorted(set(visual_statuses))) or "unavailable"
            coverage["visual"] = f"DEGRADED_VISUAL_ARTIFACTS:{status_label}"
        else:
            coverage["visual"] = "MISSING_VISUAL_ARTIFACTS"
        coverage["frame_sampling"] = "MANIFEST_ONLY"

    if layers["transcripts"]:
        transcript = transcripts.get(video_id)
        if transcript and transcript.get("transcript_available"):
            coverage["transcripts"] = "OK"
        elif transcript:
            coverage["transcripts"] = f"NO_TRANSCRIPT:{transcript.get('status') or 'missing'}"
        else:
            coverage["transcripts"] = "MISSING_TRANSCRIPT_ARTIFACTS"

    item["extracted_features"] = list(features.values())
    item["feature_ids"] = sorted({feature["id"] for feature in item["extracted_features"]})
    item["feature_sources"] = sorted({feature["source"] for feature in item["extracted_features"]})
    item["data_coverage"] = coverage


def is_niche_match(item: dict[str, Any], config: dict[str, Any]) -> bool:
    keywords = [str(value).lower() for value in (config.get("niche_keywords") or [])]
    if not keywords:
        return True
    haystack = clean_join([
        item.get("title"),
        item.get("description_snippet"),
        " ".join(item.get("queries") or []),
        " ".join(item.get("watchlist_tags") or []),
    ])
    return any(contains_keyword(haystack, keyword) for keyword in keywords)


def evidence_quality(item: dict[str, Any]) -> float:
    sample_size = safe_int(item.get("channel_baseline_sample_size"))
    sample_score = 1.0 if sample_size >= 10 else 0.8 if sample_size >= 5 else 0.0
    topic_score = 1.0 if item.get("topic_baseline_status") == "OK" else 0.0
    comments_score = 1.0 if (item.get("data_coverage") or {}).get("comments") == "OK" else 0.0
    visual_score = 1.0 if (item.get("data_coverage") or {}).get("visual") == "OK" else 0.0
    quality = sample_score * 0.68 + topic_score * 0.16 + comments_score * 0.08 + visual_score * 0.08
    return round(min(quality, 1.0), 3)


def classify_breakout(item: dict[str, Any], thresholds: dict[str, Any]) -> str:
    if item.get("channel_baseline_status") != "OK":
        return str(item.get("channel_baseline_status") or "NO_CHANNEL_BASELINE")
    multiplier = item.get("channel_outlier_multiplier")
    if multiplier is None:
        return "NO_CHANNEL_OUTLIER_MULTIPLIER"
    if multiplier >= float(thresholds.get("extreme", 20.0)):
        return "EXTREME_BREAKOUT"
    if multiplier >= float(thresholds.get("breakout", 10.0)):
        return "BREAKOUT"
    if multiplier >= float(thresholds.get("strong", 5.0)):
        return "STRONG_CHANNEL_OUTLIER"
    return "BELOW_BREAKOUT_THRESHOLD"


def rank_outliers(videos: list[dict[str, Any]], config: dict[str, Any], top_n: int) -> list[dict[str, Any]]:
    thresholds = config.get("thresholds") or {}
    strong = float(thresholds.get("strong", 5.0))
    for item in videos:
        item["breakout_status"] = classify_breakout(item, thresholds)
        item["ranking_components"] = {
            "channel_outlier_multiplier": item.get("channel_outlier_multiplier"),
            "evidence_quality": evidence_quality(item),
            "topic_ratio": item.get("topic_ratio"),
            "views_per_day": item.get("views_per_day"),
            "views": item.get("views"),
        }
        item["ranking_sort_order"] = [
            "channel_outlier_multiplier",
            "evidence_quality",
            "topic_ratio",
            "views_per_day",
            "views",
        ]

    ranked = [
        item for item in videos
        if item.get("channel_baseline_status") == "OK"
        and (item.get("channel_outlier_multiplier") or 0) >= strong
    ]
    ranked.sort(
        key=lambda item: (
            item.get("channel_outlier_multiplier") or 0.0,
            item["ranking_components"]["evidence_quality"] or 0.0,
            item.get("topic_ratio") or 0.0,
            math.log10((item.get("views_per_day") or 0) + 1),
            math.log10((item.get("views") or 0) + 1),
        ),
        reverse=True,
    )
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    return ranked[:top_n]


def median_or_zero(values: list[float]) -> float:
    return float(median(values)) if values else 0.0


def pattern_confidence(
    *,
    evidence_count: int,
    channels_count: int,
    median_multiplier: float,
    adequate_baselines: int,
    source_types: set[str],
) -> str:
    if (
        evidence_count >= 3
        and channels_count >= 2
        and median_multiplier >= 10
        and adequate_baselines >= 3
        and len(source_types) >= 2
    ):
        return "HIGH"
    if evidence_count >= 2 and channels_count >= 2 and median_multiplier >= 5 and adequate_baselines >= 2:
        return "MEDIUM"
    return "LOW"


def compact_example(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": item.get("title"),
        "channel_name": item.get("channel_name"),
        "video_url": item.get("video_url"),
        "views": item.get("views"),
        "channel_outlier_multiplier": item.get("channel_outlier_multiplier"),
        "breakout_status": item.get("breakout_status"),
    }


def build_patterns(videos: list[dict[str, Any]], ranked: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    ranked_keys = {item.get("video_id") or item.get("video_url") for item in ranked}
    by_pattern: dict[str, dict[str, Any]] = {}
    all_with_pattern: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in videos:
        seen_ids = set()
        for feature in item.get("extracted_features") or []:
            pattern_id = feature["id"]
            if pattern_id not in seen_ids:
                all_with_pattern[pattern_id].append(item)
                seen_ids.add(pattern_id)
            if (item.get("video_id") or item.get("video_url")) not in ranked_keys:
                continue
            group = by_pattern.setdefault(pattern_id, {
                "pattern": feature["pattern"],
                "niche": config["niche"],
                "items": {},
                "source_types": set(),
            })
            item_key = item.get("video_id") or item.get("video_url") or item.get("title")
            group["items"][item_key] = item
            group["source_types"].add(feature["source"])

    rows: list[dict[str, Any]] = []
    for pattern_id, group in by_pattern.items():
        evidence_items = list(group["items"].values())
        channels = {item.get("channel_url") or item.get("channel_name") for item in evidence_items if item.get("channel_url") or item.get("channel_name")}
        multipliers = [float(item.get("channel_outlier_multiplier") or 0) for item in evidence_items if item.get("channel_outlier_multiplier")]
        adequate = sum(1 for item in evidence_items if item.get("channel_baseline_status") == "OK")
        source_types = set(group["source_types"])
        counterexamples = [
            item for item in all_with_pattern.get(pattern_id, [])
            if (item.get("video_id") or item.get("video_url")) not in ranked_keys
        ]
        counterexamples.sort(key=lambda item: item.get("channel_outlier_multiplier") or 0, reverse=True)
        med = round(median_or_zero(multipliers), 2)
        confidence = pattern_confidence(
            evidence_count=len(evidence_items),
            channels_count=len(channels),
            median_multiplier=med,
            adequate_baselines=adequate,
            source_types=source_types,
        )
        rows.append({
            "pattern": group["pattern"],
            "niche": config["niche"],
            "evidence_count": len(evidence_items),
            "channels_count": len(channels),
            "median_outlier_multiplier": med,
            "examples": [compact_example(item) for item in evidence_items[:5]],
            "counterexamples": [compact_example(item) for item in counterexamples[:5]],
            "confidence": confidence,
            "source_types": sorted(source_types),
            "interpretation": (
                f"Observed with {len(evidence_items)} qualified breakout video(s) across {len(channels)} channel(s). "
                "Treat as a production hypothesis to test, not a causal claim."
            ),
            "causality_warning": CAUSALITY_WARNING,
        })
    rows.sort(
        key=lambda item: (
            {"HIGH": 3, "MEDIUM": 2, "LOW": 1}[item["confidence"]],
            item["channels_count"],
            item["evidence_count"],
            item["median_outlier_multiplier"],
        ),
        reverse=True,
    )
    return rows


def build_visual_manifest(videos: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    return {
        "niche": config["niche"],
        "purpose": "Provider-neutral manifest for optional public thumbnail/frame vision analysis.",
        "provider_binding": "none",
        "frame_policy": {
            "sample_points": FRAME_SAMPLE_POINTS,
            "max_resolution_note": "Use low-resolution sampled frames; do not download full 4K videos when samples are enough.",
        },
        "items": [
            {
                "video_id": item.get("video_id"),
                "title": item.get("title"),
                "video_url": item.get("video_url"),
                "thumbnail_url": item.get("thumbnail_url"),
                "suggested_frame_samples": FRAME_SAMPLE_POINTS,
            }
            for item in videos
            if item.get("video_url") or item.get("thumbnail_url")
        ],
    }


def summarize_coverage(videos: list[dict[str, Any]]) -> dict[str, Any]:
    fields = ["metadata", "comments", "visual", "transcripts", "frame_sampling", "audio"]
    summary: dict[str, Any] = {}
    gaps: list[dict[str, Any]] = []
    for field in fields:
        counts = Counter((item.get("data_coverage") or {}).get(field, "UNKNOWN") for item in videos)
        summary[field] = dict(counts)
        for status, count in counts.items():
            if status not in {"OK", "NOT_REQUESTED", "MANIFEST_ONLY"}:
                gaps.append({"layer": field, "status": status, "videos": count})
    return {"summary": summary, "gaps": gaps}


def split_small_established(ranked: list[dict[str, Any]], config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    limit = float((config.get("small_channel") or {}).get("median_views_max") or 50000)
    small: list[dict[str, Any]] = []
    established: list[dict[str, Any]] = []
    for item in ranked:
        median_views = item.get("channel_recent_median_views") or 0
        if median_views <= limit:
            small.append(item)
        else:
            established.append(item)
    return small, established


def render_video_line(item: dict[str, Any]) -> str:
    topic = item.get("topic_baseline") or {}
    return (
        f"- **{item.get('title') or 'Untitled'}** | {item.get('channel_name') or 'Unknown'} | "
        f"views: {safe_int(item.get('views'))} | median: {item.get('channel_recent_median_views')} | "
        f"channel multiplier: {item.get('channel_outlier_multiplier')}x ({item.get('channel_outlier_tier')}) | "
        f"views/day: {item.get('views_per_day')} | topic ratio: {topic.get('topic_ratio')} | "
        f"comments/1k views: {item.get('comment_rate_per_1000_views')} | status: {item.get('breakout_status')} | "
        f"{item.get('video_url') or 'no url'}"
    )


def render_pattern_line(pattern: dict[str, Any]) -> str:
    return (
        f"- **{pattern['pattern']}** | evidence: {pattern['evidence_count']} | "
        f"channels: {pattern['channels_count']} | median multiplier: {pattern['median_outlier_multiplier']}x | "
        f"sources: {', '.join(pattern.get('source_types') or []) or 'metadata only'} | "
        f"confidence: {pattern['confidence']} | warning: {pattern['causality_warning']}"
    )


def render_report(analysis: dict[str, Any]) -> str:
    ranked = analysis["ranked_outliers"]
    small = analysis["top_small_channel_breakouts"]
    established = analysis["top_established_channel_breakouts"]
    patterns = analysis["patterns"]
    cross_patterns = [pattern for pattern in patterns if pattern.get("channels_count", 0) >= 2]
    gaps = analysis["data_coverage"]["gaps"]
    confidence_counts = Counter(pattern["confidence"] for pattern in patterns)
    pattern_categories = (analysis.get("PATTERN_BANK") or {}).get("categories") or {}

    lines = [
        f"# YouTube Breakout Analyzer - {analysis['niche']['label']}",
        "",
        "## Verdict",
        f"Facts: {analysis['facts']['videos_analyzed']} niche-matched public video record(s), {analysis['facts']['ranked_outliers']} qualified breakout(s), {analysis['facts']['channels_analyzed']} channel(s).",
        "Computed signals: ranking uses visible channel multiplier, evidence quality, topic ratio, views/day, then raw views.",
        "Interpretation / hypotheses: repeated patterns below are candidates for controlled production tests.",
        f"Warning: {CAUSALITY_WARNING}. Public data does not include CTR, retention, traffic source, or YouTube Studio internals.",
        "",
        "## Data coverage and access gaps",
        f"- Mode: {analysis['mode']}",
        f"- Latest pointer: {analysis['outputs'].get('latest_pointer')}",
        f"- Search bundle: {analysis['input_summary'].get('search_bundle_path') or 'not found'}",
        f"- Excluded as outside niche: {analysis['facts']['excluded_non_niche']}",
    ]
    if gaps:
        for gap in gaps:
            lines.append(f"- Gap: {gap['layer']} -> {gap['status']} ({gap['videos']} video(s))")
    else:
        lines.append("- No access gaps for requested layers.")
    lines.extend([
        "",
        "## Top small-channel breakouts",
    ])
    if small:
        lines.extend(render_video_line(item) for item in small[:10])
    else:
        lines.append("- None qualified with the current channel-baseline threshold.")
    lines.append("")
    lines.append("## Top established-channel breakouts")
    if established:
        lines.extend(render_video_line(item) for item in established[:10])
    else:
        lines.append("- None qualified with the current channel-baseline threshold.")
    lines.extend(["", "## Repeated patterns", "", "### Cross-channel patterns"])
    if cross_patterns:
        lines.extend(render_pattern_line(pattern) for pattern in cross_patterns[:10])
    else:
        lines.append("- No pattern repeated across multiple channels at the current threshold.")
    lines.extend(["", "## Niche-specific patterns"])
    if patterns:
        lines.extend(render_pattern_line(pattern) for pattern in patterns[:12])
    else:
        lines.append("- No niche-specific pattern has enough qualified evidence yet.")
    lines.extend(["", "## Counterexamples / killed hypotheses"])
    any_counter = False
    for pattern in patterns[:8]:
        if not pattern.get("counterexamples"):
            continue
        any_counter = True
        lines.append(f"- **{pattern['pattern']}** has non-breakout examples:")
        for item in pattern["counterexamples"][:3]:
            lines.append(
                f"  - {item.get('title') or 'Untitled'} | {item.get('channel_name') or 'Unknown'} | "
                f"multiplier: {item.get('channel_outlier_multiplier')} | status: {item.get('breakout_status')}"
            )
    if not any_counter:
        lines.append("- No counterexamples were present in the local niche-matched sample.")
    lines.extend(["", "## PATTERN_BANK"])
    for category in PATTERN_BANK_CATEGORIES:
        values = pattern_categories.get(category) or []
        if category == "avoid_copying":
            lines.append(f"- **{category}**: {len(values)} guardrail(s); see `PATTERN_BANK.md`.")
        else:
            lines.append(f"- **{category}**: {len(values)} qualified pattern(s).")
    lines.extend([
        "",
        "## Facts vs interpretation",
        "- Facts: public titles, URLs, channels, view counts, comment counts, publish dates, local comments/artifacts when present.",
        "- Computed signals: video age, views/day, channel multiplier, topic ratio, comment rate, evidence quality, pattern counts.",
        "- Interpretation/hypotheses: any packaging, route, title, thumbnail, or audience-motivation pattern.",
        f"- Causality boundary: {CAUSALITY_WARNING}.",
        "",
        "## Main caveat",
        "- This is public evidence only. It cannot verify impressions, CTR, retention, traffic sources, revenue, conversion, subscriber notifications, paid promotion, or creator-side edits.",
        "",
        "## Limitations",
        "- Public collection can be incomplete, rate-limited, region-dependent, or temporarily unavailable.",
        "- Unknown values remain unknown; missing optional layers are never converted to zero.",
        "- Statistical association does not prove why a video succeeded and does not guarantee virality.",
        "",
        "## Recommended experiments",
    ])
    if patterns:
        for pattern in patterns[:5]:
            lines.append(
                f"- Test `{pattern['pattern']}` as one controlled variable. Keep topic/channel context stable and compare 7-day and 28-day metrics."
            )
    else:
        lines.append("- Collect more channel baselines and comments before making a production experiment.")
    lines.extend([
        "",
        "## Confidence",
        f"- HIGH patterns: {confidence_counts.get('HIGH', 0)}",
        f"- MEDIUM patterns: {confidence_counts.get('MEDIUM', 0)}",
        f"- LOW patterns: {confidence_counts.get('LOW', 0)}",
        "- Confidence increases with repetition across channels, strong normalized outliers, adequate channel baselines, and agreement across metadata/comments/visual artifacts.",
    ])
    return "\n".join(lines).strip() + "\n"


def best_pattern_label(patterns: list[dict[str, Any]], prefix: str, fallback: str) -> str:
    for pattern in patterns:
        if pattern["pattern"].startswith(prefix):
            return pattern["pattern"].split(":", 1)[-1].strip()
    return fallback


def playbook_evidence_patterns(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        pattern for pattern in patterns
        if pattern.get("confidence") in {"MEDIUM", "HIGH"}
        and safe_int(pattern.get("evidence_count")) >= 2
        and safe_int(pattern.get("channels_count")) >= 2
    ]


def evidence_titles(patterns: list[dict[str, Any]], limit: int = 3) -> list[str]:
    titles: list[str] = []
    for pattern in patterns:
        for example in pattern.get("examples") or []:
            title = example.get("title")
            if title and title not in titles:
                titles.append(title)
            if len(titles) >= limit:
                return titles
    return titles


def render_playbook(analysis: dict[str, Any]) -> str:
    patterns = playbook_evidence_patterns(analysis["patterns"])
    if not patterns:
        return "\n".join([
            f"# Content Playbook - {analysis['niche']['label']}",
            "",
            "INSUFFICIENT_EVIDENCE",
            "",
            "No recurring cross-channel pattern met the minimum evidence threshold for a production playbook.",
        ]) + "\n"

    examples = evidence_titles(patterns)
    playbook_type = analysis["niche"].get("playbook_type")
    if playbook_type == "walking":
        lines = [
            "# Shooting Playbook - Walking",
            "",
            f"Viewer job: {best_pattern_label(patterns, 'audience_motivation:', 'INSUFFICIENT_EVIDENCE')}",
            f"Location: {best_pattern_label(patterns, 'city:', 'INSUFFICIENT_EVIDENCE')}",
            f"Rare condition / moment: {best_pattern_label(patterns, 'weather:', 'INSUFFICIENT_EVIDENCE')}",
            "Opening 30 seconds: Start with immediate place/context signal, stable movement, and ambient sound if available.",
            "Route arc: Move from a readable starting point through a distinct middle section toward one visual payoff.",
            f"Visual payoffs: {best_pattern_label(patterns, 'thumbnail:', 'INSUFFICIENT_EVIDENCE')}",
            f"Duration range from evidence: {best_pattern_label(patterns, 'duration:', 'INSUFFICIENT_EVIDENCE')}",
            "Camera movement notes: Keep pace steady; avoid rapid pans unless the route payoff requires it.",
            "Audio notes: Use real ambient sound where possible; mark speech/music/wind gaps explicitly during review.",
            "Title formula: place + condition + moment + format, with resolution/no-talking markers only when true.",
            "Thumbnail formula: one clear route payoff; avoid implying unavailable frame evidence.",
            "Evidence examples:",
        ]
        lines.extend(f"- {title}" for title in examples or ["No qualified example yet."])
        lines.extend([
            "What is hypothesis vs proven repetition:",
            f"- Observed repetition is evidence for association only; {CAUSALITY_WARNING}.",
        ])
        return "\n".join(lines).strip() + "\n"

    if playbook_type in {"generic", "content", None}:
        lines = [
            "# Content Experiment Brief - Generic",
            "",
            f"Audience promise: {best_pattern_label(patterns, 'audience_promise:', 'INSUFFICIENT_EVIDENCE')}",
            f"Title formula: {best_pattern_label(patterns, 'title_formula:', 'INSUFFICIENT_EVIDENCE')}",
            f"Format: {best_pattern_label(patterns, 'format:', 'INSUFFICIENT_EVIDENCE')}",
            f"Thumbnail signal: {best_pattern_label(patterns, 'thumbnail:', 'INSUFFICIENT_EVIDENCE')}",
            f"Duration range from evidence: {best_pattern_label(patterns, 'duration:', 'INSUFFICIENT_EVIDENCE')}",
            "Controlled variable: Change one observed pattern per upload.",
            "Evidence examples:",
        ]
        lines.extend(f"- {title}" for title in examples)
        lines.extend([
            "What is hypothesis vs proven repetition:",
            f"- Observed repetition is evidence for association only; {CAUSALITY_WARNING}.",
        ])
        return "\n".join(lines).strip() + "\n"

    lines = [
        "# Content Experiment Brief - AI Automation",
        "",
        f"Audience job: {best_pattern_label(patterns, 'audience_signal:', 'INSUFFICIENT_EVIDENCE')}",
        f"Tool/product: {best_pattern_label(patterns, 'tool_product:', 'INSUFFICIENT_EVIDENCE')}",
        f"Concrete use case: {best_pattern_label(patterns, 'concrete_use_case:', 'INSUFFICIENT_EVIDENCE')}",
        f"Format: {best_pattern_label(patterns, 'format:', 'INSUFFICIENT_EVIDENCE')}",
        f"Proof/result: {best_pattern_label(patterns, 'proof:', 'INSUFFICIENT_EVIDENCE')}",
        "Controlled variable: Change one packaging/content variable per upload.",
        "Title formula: tool + use case + specific result or constraint.",
        "Thumbnail formula: recognizable workflow/proof element; do not imply private metrics you do not have.",
        "Evidence examples:",
    ]
    lines.extend(f"- {title}" for title in examples or ["No qualified example yet."])
    lines.extend([
        "What is hypothesis vs proven repetition:",
        f"- Observed repetition is evidence for association only; {CAUSALITY_WARNING}.",
    ])
    return "\n".join(lines).strip() + "\n"


def csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return str(value)
    return value


def write_csv(path: Path, videos: list[dict[str, Any]]) -> None:
    fields = [
        "rank",
        "breakout_status",
        "title",
        "channel_name",
        "video_url",
        "views",
        "published_at",
        "video_age_days",
        "views_per_day",
        "comments_count",
        "comment_rate_per_1000_views",
        "comments_per_day",
        "channel_recent_median_views",
        "channel_baseline_sample_size",
        "channel_baseline_status",
        "channel_outlier_multiplier",
        "channel_outlier_tier",
        "topic_key",
        "topic_median_views_per_day",
        "topic_ratio",
        "topic_baseline_sample_size",
        "topic_baseline_status",
        "comment_multiplier",
        "evidence_quality",
        "feature_ids",
        "coverage",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for item in videos:
            topic = item.get("topic_baseline") or {}
            row = {
                **{field: item.get(field) for field in fields},
                "topic_key": topic.get("topic_key"),
                "evidence_quality": (item.get("ranking_components") or {}).get("evidence_quality"),
                "feature_ids": "|".join(item.get("feature_ids") or []),
                "coverage": ";".join(f"{key}={value}" for key, value in (item.get("data_coverage") or {}).items()),
            }
            writer.writerow({key: csv_value(value) for key, value in row.items()})


def build_pattern_bank(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert observed associations into explicitly testable production hypotheses."""
    bank: list[dict[str, Any]] = []
    for item in patterns:
        examples = item.get("examples") or []
        counterexamples = item.get("counterexamples") or []
        known = [
            f"Observed in {item.get('evidence_count', 0)} qualified breakout video(s)",
            f"Observed across {item.get('channels_count', 0)} channel(s)",
            f"Median channel multiplier: {item.get('median_outlier_multiplier')}",
        ]
        unknown = [
            "Whether the pattern caused the result",
            "Whether the association transfers to a different channel or audience",
            "How packaging, timing, topic demand, and distribution interacted",
        ]
        bank.append({
            "pattern": item.get("pattern"),
            "evidence_count": item.get("evidence_count", len(examples)),
            "channels_count": item.get("channels_count", 0),
            "median_breakout_multiplier": item.get("median_outlier_multiplier"),
            "examples": examples,
            "evidence": examples,
            "counterexamples": counterexamples,
            "explanation": item.get("interpretation") or f"This feature repeated among qualified channel-normalized outliers in the observed sample.",
            "production_hypothesis": f"Test '{item.get('pattern')}' while keeping topic, publishing window, and production quality as stable as practical.",
            "confidence": item.get("confidence") or "LOW",
            "known": known,
            "unknown": unknown,
            "next_test": {
                "change": item.get("pattern"),
                "hold_constant": ["topic intent", "publishing window", "production quality"],
                "measure": ["channel-normalized views", "views per day", "comment rate"],
                "decision_rule": "Keep only if the controlled test beats the channel baseline; one result is not proof.",
            },
            "causality_warning": CAUSALITY_WARNING,
        })
    return bank


PATTERN_BANK_CATEGORIES = [
    "title_formulas",
    "thumbnail_formulas",
    "content_formats",
    "audience_promises",
    "emotional_hooks",
    "comment_motivations",
    "saturation_signals",
    "opportunity_gaps",
    "counter_patterns",
    "avoid_copying",
]


def structure_pattern_bank(entries: list[dict[str, Any]]) -> dict[str, Any]:
    bank: dict[str, Any] = {key: [] for key in PATTERN_BANK_CATEGORIES}
    for item in entries:
        name = str(item.get("pattern") or "").lower()
        if name.startswith(("title_", "title:", "title ")):
            bank["title_formulas"].append(item)
        if name.startswith("thumbnail:"):
            bank["thumbnail_formulas"].append(item)
        if name.startswith(("duration:", "production_marker:", "format:", "place_type:", "weather:", "time:")):
            bank["content_formats"].append(item)
        if name.startswith(("title_promise:", "audience_promise:")):
            bank["audience_promises"].append(item)
        if name.startswith(("emotional_hook:", "emotion:")):
            bank["emotional_hooks"].append(item)
        if name.startswith(("audience_motivation:", "comment_", "viewer_job:")):
            bank["comment_motivations"].append(item)
        if "saturation" in name:
            bank["saturation_signals"].append(item)
        if "opportunity" in name or "gap" in name:
            bank["opportunity_gaps"].append(item)
        if item.get("counterexamples"):
            bank["counter_patterns"].append(item)
    bank["avoid_copying"] = [
        "Do not copy another channel's identity, face, title, thumbnail text, or composition verbatim.",
        "Adapt the tested principle to a distinct audience promise and original execution.",
        "Treat every pattern as an association to test, not a causal recipe or virality guarantee.",
    ]
    return {
        "schema_version": "pattern-bank-v1",
        "causality_warning": CAUSALITY_WARNING,
        "categories": bank,
        "all_patterns": entries,
    }


def render_pattern_bank(pattern_bank: dict[str, Any]) -> str:
    lines = [
        "# PATTERN_BANK",
        "",
        "> Observed associations are not proven causes. Each entry is a hypothesis for a controlled test.",
        "",
    ]
    categories = pattern_bank.get("categories") or {}
    entries = pattern_bank.get("all_patterns") or []
    if not entries:
        lines += ["No qualified recurring patterns were found.", "", "Next step: collect more channel baselines and public metadata."]
        return "\n".join(lines) + "\n"
    for category in PATTERN_BANK_CATEGORIES:
        lines += [f"## {category}", ""]
        values = categories.get(category) or []
        if category == "avoid_copying":
            lines.extend(f"- {value}" for value in values)
            lines.append("")
            continue
        if not values:
            lines += ["- No qualified pattern in the current sample.", ""]
            continue
        for item in values:
            lines += [
                f"### {item['pattern']}",
                f"- Evidence count: {item['evidence_count']}",
                f"- Different channels: {item['channels_count']}",
                f"- Median breakout multiplier: {item['median_breakout_multiplier']}x",
                f"- Confidence: **{item['confidence']}**",
                f"- Counterexamples: {len(item['counterexamples'])}",
                f"- Explanation: {item['explanation']}",
                f"- Production hypothesis: {item['production_hypothesis']}",
                f"- Next test: change `{item['next_test']['change']}`; measure {', '.join(item['next_test']['measure'])}.",
                f"- Warning: {item['causality_warning']}",
                "- Examples:",
            ]
            examples = item.get("examples") or []
            lines.extend(
                f"  - [{example.get('title') or 'Untitled'}]({example.get('video_url') or '#'}) — {example.get('channel_name') or 'Unknown channel'}"
                for example in examples[:5]
            )
            if not examples:
                lines.append("  - No shareable example URL in the current sample.")
            lines.append("")
    return "\n".join(lines)


def build_source_ledger(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in analysis.get("videos") or []:
        coverage = item.get("data_coverage") or {}
        rows.append({
            "video_id": item.get("video_id"),
            "title": item.get("title"),
            "video_url": item.get("video_url"),
            "channel_name": item.get("channel_name"),
            "channel_url": item.get("channel_url"),
            "published_at": item.get("published_at"),
            "collected_at": item.get("collected_at"),
            "sources": item.get("sources") or [],
            "queries": item.get("queries") or [],
            "metadata_status": coverage.get("metadata"),
            "comments_status": coverage.get("comments"),
            "visual_status": coverage.get("visual"),
            "transcript_status": coverage.get("transcripts"),
            "baseline_status": item.get("channel_baseline_status"),
            "evidence_quality": (item.get("ranking_components") or {}).get("evidence_quality"),
        })
    return rows


def write_source_ledger_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "video_id", "title", "video_url", "channel_name", "channel_url",
        "published_at", "collected_at", "sources", "queries", "metadata_status",
        "comments_status", "visual_status", "transcript_status", "baseline_status",
        "evidence_quality",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fields})


def write_outputs(analysis: dict[str, Any], out_dir: Path, run_id: str, project_root: Path) -> dict[str, str]:
    run_id = validate_path_slug(run_id, field="run_id")
    runs_root = out_dir / "breakout-runs"
    run_dir = safe_child_path(runs_root, run_id, field="run_id")
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(
            f"run output already exists and will not be overwritten: {public_path_label(run_dir, project_root)}"
        ) from exc
    latest_paths = {
        "analysis_json": out_dir / "breakout-analysis.json",
        "analysis_csv": out_dir / "breakout-analysis.csv",
        "report_md": out_dir / "breakout-report.md",
        "playbook_md": out_dir / "content-playbook.md",
        "shooting_playbook_md": out_dir / "shooting-playbook.md",
        "pattern_bank_json": out_dir / "PATTERN_BANK.json",
        "pattern_bank_md": out_dir / "PATTERN_BANK.md",
        "source_ledger_json": out_dir / "source-ledger.json",
        "source_ledger_csv": out_dir / "source-ledger.csv",
        "visual_manifest_json": out_dir / "breakout-visual-manifest.json",
        "latest_pointer": out_dir / "breakout-latest.json",
    }
    run_paths = {
        "analysis_json": run_dir / "breakout-analysis.json",
        "analysis_csv": run_dir / "breakout-analysis.csv",
        "report_md": run_dir / "breakout-report.md",
        "playbook_md": run_dir / "content-playbook.md",
        "shooting_playbook_md": run_dir / "shooting-playbook.md",
        "pattern_bank_json": run_dir / "PATTERN_BANK.json",
        "pattern_bank_md": run_dir / "PATTERN_BANK.md",
        "source_ledger_json": run_dir / "source-ledger.json",
        "source_ledger_csv": run_dir / "source-ledger.csv",
        "visual_manifest_json": run_dir / "breakout-visual-manifest.json",
    }

    output_map = {key: public_path_label(path, project_root) or path.name for key, path in latest_paths.items()}
    analysis["outputs"] = output_map
    report = render_report(analysis)
    playbook = render_playbook(analysis)
    manifest = analysis["visual_manifest"]
    pattern_bank = analysis.get("PATTERN_BANK") or structure_pattern_bank(
        analysis.get("pattern_bank") or build_pattern_bank(analysis.get("patterns") or [])
    )
    ledger = build_source_ledger(analysis)
    pattern_bank_md = render_pattern_bank(pattern_bank)

    serializable = dict(analysis)
    write_json(run_paths["analysis_json"], serializable)
    write_json(latest_paths["analysis_json"], serializable)
    write_csv(run_paths["analysis_csv"], analysis["videos"])
    write_csv(latest_paths["analysis_csv"], analysis["videos"])
    write_text(run_paths["report_md"], report)
    write_text(latest_paths["report_md"], report)
    write_text(run_paths["playbook_md"], playbook)
    write_text(latest_paths["playbook_md"], playbook)
    write_text(run_paths["shooting_playbook_md"], playbook)
    write_text(latest_paths["shooting_playbook_md"], playbook)
    write_json(run_paths["pattern_bank_json"], pattern_bank)
    write_json(latest_paths["pattern_bank_json"], pattern_bank)
    write_text(run_paths["pattern_bank_md"], pattern_bank_md)
    write_text(latest_paths["pattern_bank_md"], pattern_bank_md)
    write_json(run_paths["source_ledger_json"], ledger)
    write_json(latest_paths["source_ledger_json"], ledger)
    write_source_ledger_csv(run_paths["source_ledger_csv"], ledger)
    write_source_ledger_csv(latest_paths["source_ledger_csv"], ledger)
    write_json(run_paths["visual_manifest_json"], manifest)
    write_json(latest_paths["visual_manifest_json"], manifest)

    pointer = {
        "run_id": run_id,
        "generated_at": analysis["generated_at"],
        "latest": {key: public_path_label(path, project_root) or path.name for key, path in latest_paths.items() if key != "latest_pointer"},
        "run": {key: public_path_label(path, project_root) or path.name for key, path in run_paths.items()},
    }
    write_json(latest_paths["latest_pointer"], pointer)
    return output_map


def compact_video_for_json(item: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "rank",
        "breakout_status",
        "video_id",
        "title",
        "video_url",
        "channel_name",
        "channel_url",
        "views",
        "published_at",
        "collected_at",
        "duration",
        "video_age_days",
        "views_per_day",
        "comments_count",
        "comment_rate_per_1000_views",
        "comments_per_day",
        "channel_recent_median_views",
        "channel_median_comments",
        "channel_baseline_sample_size",
        "channel_baseline_status",
        "channel_outlier_multiplier",
        "channel_outlier_tier",
        "comment_multiplier",
        "topic_baseline_status",
        "topic_median_views_per_day",
        "topic_ratio",
        "topic_baseline_sample_size",
        "topic_baseline",
        "ranking_components",
        "ranking_sort_order",
        "extracted_features",
        "feature_ids",
        "feature_sources",
        "data_coverage",
        "queries",
        "sources",
    ]
    return {key: item.get(key) for key in keys if key in item}


def analyze_project(options: AnalysisOptions) -> dict[str, Any]:
    project_root = options.project_root.resolve()
    config = load_niche_config(project_root, options.niche_config)
    channels_file = options.channels_file or (project_root / "watchlists" / "channels.yaml")
    topics_file = options.topics_file or (project_root / "watchlists" / "topics.yaml")
    out_dir = options.out_dir or (project_root / "result")
    run_id = options.run_id or time_slug()
    generated_at = now_iso()
    analysis_at_text = options.analysis_at or generated_at
    analysis_at = parse_dt(analysis_at_text) or datetime.now(timezone.utc)

    channels = load_channel_watchlist(channels_file) if channels_file.exists() else []
    topics = load_topics(topics_file)
    baselines_by_key, baseline_rows = load_baselines(project_root)
    raw_videos, input_summary = load_candidate_videos(
        project_root,
        search_path=options.from_search,
        baseline_rows=baseline_rows,
        limit_per_channel=options.limit_per_channel,
    )
    enrich_channel_signals(raw_videos, baselines_by_key, config, analysis_at)

    layers = mode_layers(options.mode)
    comments = load_comment_artifacts(project_root) if layers["comments"] else {}
    transcripts = load_transcript_artifacts(project_root) if layers["transcripts"] else {}
    thumbnails = load_thumbnail_artifacts(project_root) if layers["visual"] else {}
    thumbnail_vision = load_thumbnail_vision_artifacts(project_root) if layers["visual"] else {}
    for item in raw_videos:
        extract_features_for_video(
            item,
            config,
            layers=layers,
            comments=comments,
            thumbnails=thumbnails,
            thumbnail_vision=thumbnail_vision,
            transcripts=transcripts,
        )
        item["niche_match"] = is_niche_match(item, config)

    videos = [item for item in raw_videos if item.get("niche_match")]
    enrich_topic_signals(videos, topics, config)
    ranked = rank_outliers(videos, config, options.top_outliers)
    small, established = split_small_established(ranked, config)
    patterns = build_patterns(videos, ranked, config)
    visual_manifest = build_visual_manifest(videos, config)
    coverage = summarize_coverage(videos)

    ranked_ids = {item.get("video_id") or item.get("video_url") for item in ranked}
    videos.sort(
        key=lambda item: (
            0 if (item.get("video_id") or item.get("video_url")) in ranked_ids else 1,
            item.get("rank") or 999999,
            -(item.get("channel_outlier_multiplier") or 0),
            -(item.get("views_per_day") or 0),
        ),
        reverse=False,
    )

    facts = {
        "videos_loaded": len(raw_videos),
        "videos_analyzed": len(videos),
        "excluded_non_niche": len(raw_videos) - len(videos),
        "ranked_outliers": len(ranked),
        "channels_analyzed": len({item.get("channel_url") or item.get("channel_name") for item in videos if item.get("channel_url") or item.get("channel_name")}),
        "watchlist_channels": len(channels),
        "baselines_loaded": len(baseline_rows),
    }
    warnings = [
        CAUSALITY_WARNING,
        "Public data only; no login, cookies, OAuth, API keys, paid services, or YouTube Studio metrics are used.",
        "Missing comments, transcripts, thumbnails, images, or frame samples are reported as access gaps.",
    ]
    analysis: dict[str, Any] = {
        "schema_version": "breakout-analyzer-v1",
        "generated_at": generated_at,
        "analysis_at": analysis_at_text,
        "project_root": ".",
        "mode": options.mode,
        "niche": {
            "name": config["niche"],
            "label": config.get("label") or config["niche"],
            "config_path": public_path_label(config.get("_path"), project_root),
            "playbook_type": config.get("playbook_type") or config["niche"],
        },
        "thresholds": config.get("thresholds"),
        "baseline_requirements": config.get("baseline"),
        "input_summary": {
            **input_summary,
            "channels_file": public_path_label(channels_file, project_root),
            "topics_file": public_path_label(topics_file, project_root),
            "topics": topics,
            "limit_per_channel": options.limit_per_channel,
            "top_outliers": options.top_outliers,
        },
        "facts": facts,
        "data_coverage": coverage,
        "warnings": warnings,
        "videos": [compact_video_for_json(item) for item in videos],
        "ranked_outliers": [compact_video_for_json(item) for item in ranked],
        "top_small_channel_breakouts": [compact_video_for_json(item) for item in small],
        "top_established_channel_breakouts": [compact_video_for_json(item) for item in established],
        "patterns": patterns,
        "pattern_bank": build_pattern_bank(patterns),
        "PATTERN_BANK": structure_pattern_bank(build_pattern_bank(patterns)),
        "visual_manifest": visual_manifest,
        "outputs": {},
    }
    outputs = write_outputs(analysis, out_dir, run_id, project_root)
    analysis["outputs"] = outputs
    write_json(out_dir / "breakout-analysis.json", analysis)
    return analysis


def options_from_args(args: argparse.Namespace) -> AnalysisOptions:
    project_root = Path(args.project_root).resolve()
    return AnalysisOptions(
        project_root=project_root,
        niche_config=Path(args.niche_config),
        channels_file=resolve_existing_path(project_root, args.channels_file) if args.channels_file else None,
        topics_file=resolve_existing_path(project_root, args.topics_file) if args.topics_file else None,
        from_search=resolve_existing_path(project_root, args.from_search) if args.from_search else None,
        limit_per_channel=args.limit_per_channel,
        top_outliers=args.top_outliers,
        mode=args.mode,
        analysis_at=args.analysis_at,
        out_dir=Path(args.out_dir).resolve() if args.out_dir else None,
        run_id=args.run_id,
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    analysis = analyze_project(options_from_args(args))
    print(analysis["outputs"]["analysis_json"])
    print(analysis["outputs"]["analysis_csv"])
    print(analysis["outputs"]["report_md"])
    print(analysis["outputs"]["playbook_md"])


if __name__ == "__main__":
    main()
