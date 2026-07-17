from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from youtube_breakout import yt_breakout_analyzer as analyzer
from youtube_breakout import yt_breakout_fixture as fixture
from youtube_breakout import yt_channel_baselines as baselines
from youtube_breakout import yt_search
from youtube_breakout.common import normalize_video_record


ROOT = Path(__file__).resolve().parents[1]
WALKING_CONFIG = ROOT / "configs" / "niches" / "walking.yaml"
AI_CONFIG = ROOT / "configs" / "niches" / "ai-automation.yaml"
GENERIC_CONFIG = ROOT / "configs" / "niches" / "generic.yaml"


def analyze(project_root: Path, config: Path, run_id: str) -> dict:
    return analyzer.analyze_project(analyzer.AnalysisOptions(
        project_root=project_root,
        niche_config=config,
        limit_per_channel=30,
        top_outliers=25,
        mode="full-public",
        analysis_at=fixture.FIXTURE_AT,
        run_id=run_id,
    ))


def test_walking_ai_and_generic_playbook_rendering_is_separate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        fixture.write_fixture_project(project_root)
        walking = analyze(project_root, WALKING_CONFIG, "playbook-walking")
        ai = analyze(project_root, AI_CONFIG, "playbook-ai")
        generic = analyze(project_root, GENERIC_CONFIG, "playbook-generic")

    walking_playbook = analyzer.render_playbook(walking)
    ai_playbook = analyzer.render_playbook(ai)
    generic_playbook = analyzer.render_playbook(generic)
    assert walking_playbook.startswith("# Shooting Playbook - Walking")
    assert "Viewer job:" in walking_playbook
    assert ai_playbook.startswith("# Content Experiment Brief - AI Automation")
    assert "Tool/product:" in ai_playbook
    assert generic_playbook.startswith("# Content Experiment Brief - Generic")
    assert "AI Automation" not in generic_playbook


def test_weak_or_empty_playbook_evidence_emits_insufficient_evidence() -> None:
    weak = {
        "niche": {"label": "Generic YouTube topic", "playbook_type": "content"},
        "patterns": [
            {
                "pattern": "format: demo",
                "confidence": "LOW",
                "evidence_count": 1,
                "channels_count": 1,
                "examples": [{"title": "Single weak example"}],
            }
        ],
    }
    empty = {"niche": {"label": "Generic YouTube topic", "playbook_type": "content"}, "patterns": []}
    for analysis in (weak, empty):
        playbook = analyzer.render_playbook(analysis)
        assert "INSUFFICIENT_EVIDENCE" in playbook
        assert "Controlled variable:" not in playbook
        assert "Title formula:" not in playbook


def test_missing_public_values_are_not_coerced_to_zero() -> None:
    record = normalize_video_record({"id": "abc123", "title": "No public counts"}, source="test")
    assert record["views"] is None
    assert record["comments_count"] is None
    assert record["likes"] is None


def test_channel_aggregate_preserves_unknown_view_total() -> None:
    [channel] = yt_search.aggregate_channels([
        {
            "channel_name": "Unknown Views",
            "channel_url": "https://www.youtube.com/@unknown",
            "views": None,
        },
    ])
    assert channel["total_views"] is None
    assert channel["usable_view_samples"] == 0


def test_baseline_sufficiency_uses_usable_view_samples() -> None:
    item = {
        "video_id": "abc123",
        "channel_name": "Fixture Channel",
        "views": 1000,
        "comments_count": None,
        "published_at": "2026-07-01T00:00:00+00:00",
    }
    baseline = {
        "channel_name": "Fixture Channel",
        "sample_size": 10,
        "usable_view_samples": 2,
        "median_views": 100,
        "median_comments": None,
    }
    analyzer.enrich_channel_signals(
        [item],
        {analyzer.norm_key("Fixture Channel"): baseline},
        {"thresholds": {}, "baseline": {"min_channel_samples": 5}},
        datetime(2026, 7, 16, tzinfo=timezone.utc),
    )
    assert item["channel_baseline_status"] == "INSUFFICIENT_CHANNEL_BASELINE"
    assert item["channel_baseline_sample_size"] == 2
    assert item["channel_outlier_multiplier"] is None


def test_build_baseline_counts_only_usable_view_samples() -> None:
    rows = [
        {"id": "a", "title": "A"},
        {"id": "b", "title": "B", "view_count": 0},
        {"id": "c", "title": "C", "view_count": 200},
    ]
    result = baselines.build_baseline(
        {"name": "Fixture Channel", "url": "https://www.youtube.com/@fixture"},
        rows,
        "2026-01-01T00:00:00+00:00",
    )
    assert result["sample_size"] == 3
    assert result["usable_view_samples"] == 1
    assert result["latest_videos"][0]["views"] is None


def test_degraded_visual_artifacts_do_not_receive_visual_evidence_credit() -> None:
    item = {
        "video_id": "abc123",
        "title": "Fixture",
        "data_coverage": {},
        "channel_baseline_sample_size": 10,
        "topic_baseline_status": "OK",
    }
    config = {"visual_features": {"thumbnail": {"high_contrast": ["high-contrast"]}}, "duration_buckets": {}}
    analyzer.extract_features_for_video(
        item,
        config,
        layers={"comments": False, "visual": True, "transcripts": False},
        comments={},
        thumbnails={
            "abc123": {
                "status": "ok",
                "visual_metrics": {"status": "visual_metrics_unavailable", "labels": ["high-contrast"]},
            }
        },
        thumbnail_vision={},
        transcripts={},
    )
    assert item["data_coverage"]["visual"].startswith("DEGRADED_VISUAL_ARTIFACTS")
    assert "thumbnail:high_contrast" not in item["feature_ids"]
    assert analyzer.evidence_quality(item) < 1.0
