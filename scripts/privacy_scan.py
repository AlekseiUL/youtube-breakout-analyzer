#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "dist", "build"}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".yaml", ".yml", ".json", ".txt", ".csv", ""}

# Fragments are joined so this scanner does not trigger on its own source.
FORBIDDEN = {
    "private workspace": "MIKE" + "_CENTER",
    "private username": "aleksej" + "ulanov",
    "private owner name": "Alek" + "sey",
    "private agent label": "Mike/" + "Hermes",
    "private specialist label": "Tu" + "co",
    "private specialist label 2": "La" + "lo",
    "private specialist label 3": "Chu" + "ck",
    "private specialist label 4": "Na" + "cho",
    "private specialist label 5": "Wal" + "ter",
    "private specialist label 6": "Je" + "sse",
    "private specialist label 7": "Ha" + "nk",
    "private product label": "SP" + "ROUT",
    "private legacy label": "Anti" + "botik",
    "private format label": "OPEN ROUTE" + " POV",
    "private profile path": ".her" + "mes/profiles",
    "private workflow label": "kan" + "ban",
}
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"(?i)bearer\s+[a-z0-9._-]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
ABSOLUTE_HOME = re.compile(r"/Users/[A-Za-z0-9._-]+/")


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path in iter_text_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(root)
        for label, needle in FORBIDDEN.items():
            if needle in text:
                findings.append(f"{rel}: {label}")
        if ABSOLUTE_HOME.search(text):
            findings.append(f"{rel}: absolute user home path")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(f"{rel}: possible secret material")
    return sorted(set(findings))


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    findings = scan(root)
    if findings:
        print("PRIVACY_SCAN_FAILED")
        for item in findings:
            print(f"- {item}")
        return 1
    print("PRIVACY_SCAN_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
