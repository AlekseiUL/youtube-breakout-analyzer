from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import privacy_scan, release_gate
from youtube_breakout import yt_breakout_analyzer as analyzer
from youtube_breakout import yt_breakout_fixture as fixture
from youtube_breakout import yt_comments
from youtube_breakout import yt_thumbnails
from youtube_breakout.common import read_json, safe_child_path


ROOT = Path(__file__).resolve().parents[1]
WALKING_CONFIG = ROOT / "configs" / "niches" / "walking.yaml"
GENERATED_SUFFIXES = {".json", ".jsonl", ".csv", ".md"}
PRIVATE_GENERATED_PATTERNS = [
    re.compile(r"/Users/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/(?:workspace|workspaces)/[A-Za-z0-9._-]+/"),
    re.compile(r"(?i)\b[a-z]:[\\/]+users[\\/]+"),
    re.compile(r"~/"),
]


def analyze_fixture(project_root: Path, *, run_id: str = "privacy-test") -> dict:
    fixture.write_fixture_project(project_root)
    return analyzer.analyze_project(analyzer.AnalysisOptions(
        project_root=project_root,
        niche_config=WALKING_CONFIG,
        limit_per_channel=30,
        top_outliers=25,
        mode="full-public",
        analysis_at=fixture.FIXTURE_AT,
        run_id=run_id,
    ))


def generated_text_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in GENERATED_SUFFIXES)


def test_generated_json_csv_markdown_do_not_leak_private_paths() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        analyze_fixture(project_root, run_id="privacy-negative")
        findings: list[str] = []
        for path in generated_text_files(project_root):
            text = path.read_text(encoding="utf-8")
            for pattern in PRIVATE_GENERATED_PATTERNS:
                if pattern.search(text):
                    findings.append(f"{path.relative_to(project_root)} matched {pattern.pattern}")
        assert findings == []


def test_legacy_absolute_baseline_paths_are_normalized_when_read() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "legacy.json"
        posix_home = "/" + "Users/example/private/baseline.json"
        windows_home = "C:" + "\\Users\\example\\run.json"
        path.write_text(
            json_payload := (
                '{"path": '
                + repr(posix_home).replace("'", '"')
                + ', "windows": '
                + repr(windows_home).replace("'", '"')
                + "}\n"
            ),
            encoding="utf-8",
        )
        payload = read_json(path)
    assert payload["path"] == "external:baseline.json"
    assert payload["windows"] == "external:run.json"


@pytest.mark.parametrize("bad_run_id", ["/tmp/evil", "../evil", "foo/bar", r"foo\bar", "bad run!"])
def test_run_id_rejects_absolute_parent_separator_and_invalid_slugs(bad_run_id: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        fixture.write_fixture_project(project_root)
        with pytest.raises(ValueError):
            analyzer.analyze_project(analyzer.AnalysisOptions(
                project_root=project_root,
                niche_config=WALKING_CONFIG,
                limit_per_channel=30,
                top_outliers=25,
                mode="metadata-only",
                analysis_at=fixture.FIXTURE_AT,
                run_id=bad_run_id,
            ))


def test_run_id_symlink_escape_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
        project_root = Path(tmp)
        fixture.write_fixture_project(project_root)
        runs_root = project_root / "result" / "breakout-runs"
        runs_root.mkdir(parents=True, exist_ok=True)
        os.symlink(Path(outside), runs_root / "escape")
        with pytest.raises(ValueError):
            analyzer.analyze_project(analyzer.AnalysisOptions(
                project_root=project_root,
                niche_config=WALKING_CONFIG,
                limit_per_channel=30,
                top_outliers=25,
                mode="metadata-only",
                analysis_at=fixture.FIXTURE_AT,
                run_id="escape",
            ))


def test_existing_run_directory_is_immutable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        analyze_fixture(project_root, run_id="immutable-run")
        original = (project_root / "result" / "breakout-runs" / "immutable-run" / "breakout-analysis.json").read_text(encoding="utf-8")
        with pytest.raises(FileExistsError):
            analyzer.analyze_project(analyzer.AnalysisOptions(
                project_root=project_root,
                niche_config=WALKING_CONFIG,
                limit_per_channel=30,
                top_outliers=25,
                mode="full-public",
                analysis_at=fixture.FIXTURE_AT,
                run_id="immutable-run",
            ))
        assert (project_root / "result" / "breakout-runs" / "immutable-run" / "breakout-analysis.json").read_text(encoding="utf-8") == original


@pytest.mark.parametrize("bad_video_id", ["/tmp/evil", "../evil", "foo/bar", r"foo\bar", "bad id!"])
def test_video_id_derived_paths_reject_hostile_ids(bad_video_id: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with pytest.raises(ValueError):
            safe_child_path(root / "comments", bad_video_id, field="video_id")
        with pytest.raises(ValueError):
            yt_thumbnails.safe_file_stem({"video_id": bad_video_id})


def test_video_id_symlink_escape_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
        comments_root = Path(tmp) / "comments"
        comments_root.mkdir(parents=True)
        os.symlink(Path(outside), comments_root / "escape")
        with pytest.raises(ValueError, match="resolved path escapes output root"):
            safe_child_path(comments_root, "escape", field="video_id")


def test_comments_payload_video_id_symlink_escape_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    comments_root = tmp_path / "comments"
    outside = tmp_path / "outside"
    comments_root.mkdir()
    outside.mkdir()
    os.symlink(outside, comments_root / "escape")
    monkeypatch.setattr(yt_comments, "COMMENTS_DIR", comments_root)
    monkeypatch.setattr(
        yt_comments,
        "parse_args",
        lambda: SimpleNamespace(
            video_id=[],
            video_url=["https://www.youtube.com/watch?v=source"],
            from_search=None,
            limit=1,
            sort=["top"],
            command_timeout_sec=1.0,
            overwrite=False,
        ),
    )
    monkeypatch.setattr(
        yt_comments,
        "fetch_comments",
        lambda *_args, **_kwargs: {"id": "escape", "comments": []},
    )

    with pytest.raises(ValueError, match="resolved path escapes output root"):
        yt_comments.main()

    assert list(outside.iterdir()) == []


def test_privacy_scanners_reject_json_escaped_windows_home_path(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    windows_home = "C:" + "\\" + "Users" + "\\" + "Alice" + "\\private\\result.json"
    artifact.write_text(
        json.dumps({"path": windows_home}),
        encoding="utf-8",
    )

    assert privacy_scan.scan(tmp_path)
    assert release_gate.scan_generated_artifacts(tmp_path)
