#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "dist", "build"}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".yaml", ".yml", ".json", ".txt", ".csv", ""}

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"(?i)bearer\s+[a-z0-9._-]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
ABSOLUTE_PATH_PATTERNS = [
    ("absolute macOS user home path", re.compile(r"/Users/[A-Za-z0-9._-]+/")),
    ("absolute POSIX user home path", re.compile(r"/home/[A-Za-z0-9._-]+/")),
    ("absolute POSIX workspace path", re.compile(r"/(?:workspace|workspaces)/[A-Za-z0-9._-]+/")),
    ("absolute Windows user home path", re.compile(r"(?i)\b[a-z]:[\\/]+users[\\/]+[^\\/]+[\\/]+")),
    ("tilde home path", re.compile(r"~/[A-Za-z0-9._/-]+")),
]


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    root_text = str(root)
    for path in iter_text_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(root)
        if root_text and root_text in text:
            findings.append(f"{rel}: absolute scan-root path")
        for label, pattern in ABSOLUTE_PATH_PATTERNS:
            if pattern.search(text):
                findings.append(f"{rel}: {label}")
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
