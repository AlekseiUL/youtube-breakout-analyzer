#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
REQUIRED = [
    "README.md", "METHODOLOGY.md", "SECURITY.md", "PRIVACY.md",
    "RELEASE_MANIFEST.md", "CHANGELOG.md", "LICENSE", "pyproject.toml",
    "skills/youtube-breakout-analyzer/SKILL.md",
]
OUTPUTS = [
    "breakout-analysis.json", "breakout-analysis.csv", "breakout-report.md",
    "content-playbook.md", "PATTERN_BANK.json", "PATTERN_BANK.md",
    "source-ledger.json", "source-ledger.csv", "breakout-visual-manifest.json",
    "breakout-latest.json",
]


def run(args: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=cwd, check=True)


def main() -> int:
    missing = [rel for rel in REQUIRED if not (ROOT / rel).exists()]
    if missing:
        print("RELEASE_GATE_FAILED missing:", ", ".join(missing))
        return 1

    run([str(PYTHON), "-m", "compileall", "-q", "youtube_breakout", "scripts"])
    run([str(PYTHON), "-m", "pytest"])
    run([str(PYTHON), "scripts/privacy_scan.py", "."])

    with tempfile.TemporaryDirectory(prefix="yba-release-") as tmp:
        project = Path(tmp) / "fixture"
        run([
            str(PYTHON), "-m", "youtube_breakout.cli", "fixture",
            "--project-root", str(project), "--niche", "walking", "--force",
        ])
        absent = [name for name in OUTPUTS if not (project / "result" / name).exists()]
        if absent:
            print("RELEASE_GATE_FAILED fixture outputs:", ", ".join(absent))
            return 1
        analysis = json.loads((project / "result/breakout-analysis.json").read_text(encoding="utf-8"))
        if not analysis.get("pattern_bank"):
            print("RELEASE_GATE_FAILED: fixture PATTERN_BANK is empty")
            return 1
        if "association, not proven cause" not in " ".join(analysis.get("warnings") or []):
            print("RELEASE_GATE_FAILED: causality warning missing")
            return 1

    print("RELEASE_GATE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
