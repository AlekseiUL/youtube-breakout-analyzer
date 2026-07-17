#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
REQUIRED = [
    "README.md", "METHODOLOGY.md", "SECURITY.md", "PRIVACY.md",
    "RELEASE_MANIFEST.md", "CHANGELOG.md", "LICENSE", "pyproject.toml",
    "skills/youtube-breakout-analyzer/SKILL.md",
]
OUTPUTS = [
    "breakout-analysis.json", "breakout-analysis.csv", "breakout-report.md",
    "content-playbook.md", "shooting-playbook.md", "PATTERN_BANK.json", "PATTERN_BANK.md",
    "source-ledger.json", "source-ledger.csv", "breakout-visual-manifest.json",
    "breakout-latest.json",
]
SECURITY_TESTS = [
    "tests/test_privacy_and_containment.py",
    "tests/test_yt_dlp_security.py",
    "tests/test_thumbnail_security.py",
    "tests/test_playbooks_and_regressions.py",
]
GENERATED_TEXT_SUFFIXES = {".json", ".jsonl", ".csv", ".md"}
GENERATED_FORBIDDEN = [
    re.compile(r"/Users/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/(?:workspace|workspaces)/[A-Za-z0-9._-]+/"),
    re.compile(r"(?i)\b[a-z]:[\\/]+users[\\/]+"),
    re.compile(r"~/"),
]


def run(args: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(display_arg(arg) for arg in args))
    subprocess.run(args, cwd=cwd, check=True, env=env)


def display_arg(arg: str) -> str:
    text = str(arg)
    home = str(Path.home())
    tmp = tempfile.gettempdir()
    if text == str(PYTHON):
        return "python"
    if text.startswith(str(ROOT)):
        rel = Path(text).resolve().relative_to(ROOT.resolve()).as_posix()
        return rel or "."
    if home and text.startswith(home):
        return "<home>" + text[len(home):]
    if tmp and text.startswith(tmp):
        return "<tmp>/" + Path(text).name
    return text


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def venv_script(venv: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return venv / ("Scripts" if os.name == "nt" else "bin") / f"{name}{suffix}"


def fail(message: str) -> int:
    print(f"RELEASE_GATE_FAILED: {message}")
    return 1


def scan_generated_artifacts(root: Path) -> list[str]:
    findings: list[str] = []
    root_text = str(root.resolve())
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in GENERATED_TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(root)
        if root_text in text:
            findings.append(f"{rel}: absolute generated root path")
        for pattern in GENERATED_FORBIDDEN:
            if pattern.search(text):
                findings.append(f"{rel}: private absolute path pattern {pattern.pattern}")
    return findings


def assert_fixture_outputs(project: Path) -> int:
    absent = [name for name in OUTPUTS if not (project / "result" / name).exists()]
    if absent:
        return fail("fixture outputs: " + ", ".join(absent))
    analysis = json.loads((project / "result/breakout-analysis.json").read_text(encoding="utf-8"))
    if not analysis.get("pattern_bank"):
        return fail("fixture PATTERN_BANK is empty")
    if "association, not proven cause" not in " ".join(analysis.get("warnings") or []):
        return fail("causality warning missing")
    findings = scan_generated_artifacts(project)
    if findings:
        print("RELEASE_GATE_FAILED generated privacy:")
        for item in findings:
            print(f"- {item}")
        return 1
    run([str(PYTHON), "scripts/privacy_scan.py", str(project)])
    return 0


def safe_extract_tar(archive: Path, dest: Path) -> None:
    with tarfile.open(archive, "r:*") as tf:
        for member in tf.getmembers():
            target = (dest / member.name).resolve()
            target.relative_to(dest.resolve())
        tf.extractall(dest)


def safe_extract_zip(archive: Path, dest: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            target = (dest / name).resolve()
            target.relative_to(dest.resolve())
        zf.extractall(dest)


def check_archive_members(archive: Path) -> int:
    if archive.suffix == ".whl":
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
    else:
        with tarfile.open(archive, "r:*") as tf:
            names = tf.getnames()
    forbidden = [name for name in names if name.startswith((".git/", ".venv/", "dist/")) or "/.env" in name or name.endswith("/.env")]
    if forbidden:
        return fail(f"forbidden archive members in {archive.name}: {', '.join(forbidden[:5])}")
    if not any("youtube_breakout/" in name for name in names):
        return fail(f"package files missing from {archive.name}")
    return 0


def build_and_check_archives(tmp: Path) -> tuple[int, Path | None]:
    dist_dir = tmp / "dist"
    run([str(PYTHON), "-m", "build", "--wheel", "--sdist", "--outdir", str(dist_dir)])
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        return fail("expected one wheel and one sdist"), None
    for archive in [wheels[0], sdists[0]]:
        rc = check_archive_members(archive)
        if rc:
            return rc, None
        extract_dir = tmp / "archives" / archive.name
        extract_dir.mkdir(parents=True, exist_ok=True)
        if archive.suffix == ".whl":
            safe_extract_zip(archive, extract_dir)
        else:
            safe_extract_tar(archive, extract_dir)
        run([str(PYTHON), "scripts/privacy_scan.py", str(extract_dir)])
    return 0, wheels[0]


def validate_skill() -> int:
    root_skill = ROOT / "SKILL.md"
    standalone = ROOT / "skills/youtube-breakout-analyzer/SKILL.md"
    if root_skill.read_text(encoding="utf-8") != standalone.read_text(encoding="utf-8"):
        return fail("standalone skill differs from root SKILL.md")
    text = standalone.read_text(encoding="utf-8")
    required = [
        "---",
        "name: youtube-breakout-analyzer",
        "description:",
        "youtube-breakout --version",
        "Never provide cookies",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        return fail("skill missing required markers: " + ", ".join(missing))
    return 0


def installed_cli_smoke(tmp: Path, wheel: Path) -> int:
    venv = tmp / "venv"
    run([str(PYTHON), "-m", "venv", str(venv)])
    vp = venv_python(venv)
    smoke_env = dict(os.environ)
    for name in ("PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE"):
        smoke_env.pop(name, None)
    path_entries = [str(vp.parent)]
    if smoke_env.get("PATH"):
        path_entries.append(smoke_env["PATH"])
    smoke_env.update({
        "PATH": os.pathsep.join(path_entries),
        "VIRTUAL_ENV": str(venv),
        "PYTHONNOUSERSITE": "1",
        "PIP_NO_CACHE_DIR": "1",
    })
    smoke_cwd = tmp / "installed-smoke"
    smoke_cwd.mkdir()
    run([str(vp), "-m", "pip", "install", "-q", str(wheel)], cwd=smoke_cwd, env=smoke_env)
    run([str(vp), "-m", "pip", "check"], cwd=smoke_cwd, env=smoke_env)
    run([
        str(vp),
        "-I",
        "-c",
        (
            "from pathlib import Path; import sys, yaml, yt_dlp, youtube_breakout; "
            "Path(youtube_breakout.__file__).resolve().relative_to(Path(sys.prefix).resolve())"
        ),
    ], cwd=smoke_cwd, env=smoke_env)
    cli = venv_script(venv, "youtube-breakout")
    run([str(cli), "--version"], cwd=smoke_cwd, env=smoke_env)
    project = tmp / "installed-init"
    run([str(cli), "init", "--project-root", str(project)], cwd=smoke_cwd, env=smoke_env)
    expected = [project / "watchlists/topics.yaml", project / "watchlists/channels.yaml", project / "result"]
    missing = [path for path in expected if not path.exists()]
    if missing:
        return fail("installed CLI init missing: " + ", ".join(path.name for path in missing))
    run([str(PYTHON), "scripts/privacy_scan.py", str(project)])
    fixture_project = tmp / "installed-fixture"
    run([
        str(cli), "fixture",
        "--project-root", str(fixture_project),
        "--niche", "walking",
        "--force",
    ], cwd=smoke_cwd, env=smoke_env)
    rc = assert_fixture_outputs(fixture_project)
    if rc:
        return rc
    return 0


def live_network_smoke(tmp: Path) -> int:
    project = tmp / "live-network-smoke"
    run([
        str(PYTHON), "-m", "youtube_breakout.cli", "search",
        "--project-root", str(project),
        "--query", "walking tour",
        "--limit", "1",
        "--timeout", "20",
    ])
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Release gate for youtube-breakout-analyzer.")
    parser.add_argument(
        "--live-network-smoke",
        action="store_true",
        help="Opt in to a best-effort live public YouTube collection smoke. Not run by default.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    missing = [rel for rel in REQUIRED if not (ROOT / rel).exists()]
    if missing:
        print("RELEASE_GATE_FAILED missing:", ", ".join(missing))
        return 1

    run([str(PYTHON), "-m", "compileall", "-q", "youtube_breakout", "scripts"])
    run([str(PYTHON), "-m", "pytest"])
    run([str(PYTHON), "-m", "pytest", *SECURITY_TESTS])
    run([str(PYTHON), "scripts/privacy_scan.py", "."])
    rc = validate_skill()
    if rc:
        return rc

    with tempfile.TemporaryDirectory(prefix="yba-release-") as tmp:
        tmp_path = Path(tmp)
        rc, wheel = build_and_check_archives(tmp_path)
        if rc:
            return rc
        if wheel is None:
            return fail("wheel unavailable after build")

        project = tmp_path / "fixture"
        run([
            str(PYTHON), "-m", "youtube_breakout.cli", "fixture",
            "--project-root", str(project), "--niche", "walking", "--force",
        ])
        rc = assert_fixture_outputs(project)
        if rc:
            return rc
        rc = installed_cli_smoke(tmp_path, wheel)
        if rc:
            return rc
        if args.live_network_smoke:
            rc = live_network_smoke(tmp_path)
            if rc:
                return rc

    print("RELEASE_GATE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
