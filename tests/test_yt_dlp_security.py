from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from youtube_breakout import common
from youtube_breakout import yt_channel_baselines
from youtube_breakout import yt_comments
from youtube_breakout import yt_search
from youtube_breakout import yt_snapshots
from youtube_breakout import yt_transcripts


def completed(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["yt-dlp"], 0, stdout=stdout, stderr="")


def test_run_yt_dlp_forces_ignore_config_and_option_sentinel(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run_command(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return completed("{}")

    monkeypatch.setattr(common, "run_command", fake_run_command)
    common.run_yt_dlp(["--dump-json"], ["--cookies=/tmp/private.txt"], timeout_sec=1)
    command = calls[0]
    assert command[1] == "--ignore-config"
    assert command[-2] == "--"
    assert command[-1] == "--cookies=/tmp/private.txt"


@pytest.mark.parametrize(
    "options",
    [
        ["--cookies", "cookies.txt"],
        ["--cookies=cookies.txt"],
        ["--cookies-from-browser", "chrome"],
        ["--config-location", "yt-dlp.conf"],
        ["--config-locations", "yt-dlp.conf"],
        ["--config-locations=yt-dlp.conf"],
        ["--ignore-config"],
        ["--"],
    ],
)
def test_run_yt_dlp_rejects_cookie_config_and_caller_sentinel(options: list[str]) -> None:
    with pytest.raises(ValueError):
        common.run_yt_dlp(options, ["https://www.youtube.com/watch?v=abc"])


def test_search_collector_uses_safe_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], list[str]]] = []

    def fake_run_yt_dlp(options: list[str], targets: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append((options, targets))
        return completed(json.dumps({"entries": []}))

    monkeypatch.setattr(yt_search, "run_yt_dlp", fake_run_yt_dlp)
    assert yt_search.fetch_search_entries_yt_dlp("ytsearch", "query", 2, 1) == []
    assert yt_search.fetch_search_entries_url("query", 2, 1) == []
    assert yt_search.fetch_channel_entries("https://www.youtube.com/@fixture", 2, 1) == []
    assert len(calls) == 3
    assert all(targets for _, targets in calls)


def test_channel_baseline_collector_uses_safe_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], list[str]]] = []

    def fake_run_yt_dlp(options: list[str], targets: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append((options, targets))
        if "--flat-playlist" in options:
            return completed(json.dumps({"entries": [{"id": "abc123"}]}))
        return completed(json.dumps({"id": "abc123"}) + "\n")

    monkeypatch.setattr(yt_channel_baselines, "run_yt_dlp", fake_run_yt_dlp)
    assert yt_channel_baselines.fetch_channel_video_urls("https://www.youtube.com/@fixture", 1, 1) == [
        "https://www.youtube.com/watch?v=abc123"
    ]
    assert yt_channel_baselines.fetch_metadata_batch(["https://www.youtube.com/watch?v=abc123"], 1)[0]["id"] == "abc123"
    assert len(calls) == 2


def test_comments_collector_uses_safe_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], list[str]]] = []

    def fake_run_yt_dlp(options: list[str], targets: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append((options, targets))
        out_template = Path(options[options.index("-o") + 1])
        (out_template.parent / "abc.info.json").write_text(
            json.dumps({"id": "abc", "comments": []}),
            encoding="utf-8",
        )
        return completed("")

    monkeypatch.setattr(yt_comments, "run_yt_dlp", fake_run_yt_dlp)
    payload = yt_comments.fetch_comments("https://www.youtube.com/watch?v=abc", "top", 1)
    assert payload["id"] == "abc"
    assert calls and calls[0][1] == ["https://www.youtube.com/watch?v=abc"]


def test_transcript_collector_uses_safe_wrapper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], list[str]]] = []

    def fake_run_yt_dlp(options: list[str], targets: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append((options, targets))
        if "--dump-single-json" in options:
            return completed(json.dumps({"id": "abc", "subtitles": {}}))
        out_template = Path(options[options.index("-o") + 1])
        (out_template.parent / "abc.en.vtt").write_text("WEBVTT\n\n00:00 --> 00:01\nhello\n", encoding="utf-8")
        return completed("")

    monkeypatch.setattr(yt_transcripts, "run_yt_dlp", fake_run_yt_dlp)
    monkeypatch.setattr(yt_transcripts, "TRANSCRIPTS_DIR", tmp_path / "transcripts")
    assert yt_transcripts.fetch_metadata("https://www.youtube.com/watch?v=abc")["id"] == "abc"
    assert yt_transcripts.download_subtitle("https://www.youtube.com/watch?v=abc", "abc", "en", False)
    assert len(calls) == 2


def test_snapshot_collector_uses_safe_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], list[str]]] = []

    def fake_run_yt_dlp(options: list[str], targets: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append((options, targets))
        if "--flat-playlist" in options:
            return completed(json.dumps({"entries": [{"id": "abc"}]}))
        return completed(json.dumps({"id": "abc"}) + "\n")

    monkeypatch.setattr(yt_snapshots, "run_yt_dlp", fake_run_yt_dlp)
    assert yt_snapshots.fetch_channel_video_urls("https://www.youtube.com/@fixture", 1) == [
        "https://www.youtube.com/watch?v=abc"
    ]
    assert yt_snapshots.fetch_metadata_batch(["https://www.youtube.com/watch?v=abc"])[0]["id"] == "abc"
    assert len(calls) == 2
