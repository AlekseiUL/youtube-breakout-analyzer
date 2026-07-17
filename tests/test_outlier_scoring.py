from __future__ import annotations

from datetime import datetime, timezone

from youtube_breakout import yt_channel_baselines as baselines
from youtube_breakout import yt_search
from youtube_breakout import yt_thumbnails


def test_channel_video_url_uses_videos_tab() -> None:
    assert baselines.channel_videos_url("https://www.youtube.com/channel/UCfixture") == "https://www.youtube.com/channel/UCfixture/videos"
    assert baselines.channel_videos_url("https://www.youtube.com/@fixture/videos") == "https://www.youtube.com/@fixture/videos"


def test_percentile_and_baseline_statistics_are_visible() -> None:
    rows = [
        {"id": "a", "title": "A", "view_count": 100, "comment_count": 10},
        {"id": "b", "title": "B", "view_count": 300, "comment_count": 30},
        {"id": "c", "title": "C", "view_count": 200, "comment_count": 20},
    ]
    channel = {"name": "Example", "url": "https://www.youtube.com/@example"}
    result = baselines.build_baseline(channel, rows, "2026-01-01T00:00:00+00:00")
    assert result["median_views"] == 200.0
    assert result["p75_views"] == 250.0
    assert result["sample_size"] == 3


def test_public_period_filter_keeps_unknown_and_recent_dates() -> None:
    now = datetime(2026, 7, 17, tzinfo=timezone.utc)
    assert yt_search.within_period({}, 30, now)
    assert yt_search.within_period({"published_at": "2026-07-01T00:00:00+00:00"}, 30, now)
    assert not yt_search.within_period({"published_at": "2025-01-01T00:00:00+00:00"}, 30, now)


def test_visual_labels_are_deterministic() -> None:
    labels = yt_thumbnails.visual_labels(60, 70, 120, 40, 80)
    assert "high-contrast" in labels
    assert "saturated/color-pop" in labels
    assert "dark" in labels
    assert "dense/text-or-detail-heavy" in labels
