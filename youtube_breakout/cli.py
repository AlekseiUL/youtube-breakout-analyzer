from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

MODES = ("metadata-only", "metadata+comments", "metadata+visual", "full-public")


def public_project_label(path: Path, root: Path | None = None) -> str:
    base = (root or Path.cwd()).resolve()
    candidate = path.resolve()
    try:
        return candidate.relative_to(base).as_posix() or "."
    except ValueError:
        return candidate.name


def package_config(name: str) -> Path:
    candidate = Path(name)
    if candidate.exists():
        return candidate.resolve()
    filename = name if name.endswith(".yaml") else f"{name}.yaml"
    resource = files("youtube_breakout").joinpath("configs", "niches", filename)
    if not resource.is_file():
        raise SystemExit(f"Unknown niche config: {name}")
    return Path(str(resource))


def ensure_project(project_root: Path, *, force: bool = False) -> None:
    for rel in (
        "watchlists", "data/search", "data/transcripts", "data/comments",
        "data/snapshots", "data/channel_baselines", "data/thumbnails",
        "data/thumbnail_vision", "result",
    ):
        (project_root / rel).mkdir(parents=True, exist_ok=True)
    defaults = {
        "watchlists/topics.yaml": "topics:\n  - your topic here\n",
        "watchlists/channels.yaml": (
            "direct:\n"
            "  # - name: Example channel\n"
            "  #   url: https://www.youtube.com/@example\n"
            "  #   enabled: true\n"
            "  #   tags: [example]\n"
            "adjacent: []\nglobal_signal: []\n"
        ),
    }
    for rel, content in defaults.items():
        path = project_root / rel
        if force or not path.exists():
            path.write_text(content, encoding="utf-8")


def run_module(module: str, project_root: Path, extra: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["YOUTUBE_INTEL_PROJECT_ROOT"] = str(project_root.resolve())
    return subprocess.run([sys.executable, "-m", f"youtube_breakout.{module}", *extra], env=env, check=check, text=True)


def add_common_project(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", type=Path, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="youtube-breakout",
        description="Find channel-normalized YouTube breakout videos from public signals.",
    )
    parser.add_argument("--version", action="version", version="youtube-breakout 0.1.0")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create an editable local analysis instance.")
    add_common_project(init)
    init.add_argument("--force", action="store_true")

    search = sub.add_parser("search", help="Collect public YouTube search metadata with yt-dlp.")
    add_common_project(search)
    search.add_argument("--query", action="append", default=[])
    search.add_argument("--period-days", type=int)
    search.add_argument("--limit", type=int, default=8, help="Results per query.")
    search.add_argument("--include-watchlist", action="store_true")
    search.add_argument("--timeout", type=float, default=15.0)

    analyze = sub.add_parser("analyze", help="Analyze already collected local public artifacts.")
    add_common_project(analyze)
    analyze.add_argument("--niche", default="generic")
    analyze.add_argument("--mode", choices=MODES, default="full-public")
    analyze.add_argument("--top", type=int, default=25)
    analyze.add_argument("--limit-per-channel", type=int, default=30)
    analyze.add_argument("--analysis-at")
    analyze.add_argument("--run-id")

    fixture = sub.add_parser("fixture", help="Create anonymous fixture data and run an offline analysis.")
    add_common_project(fixture)
    fixture.add_argument("--niche", choices=("walking", "ai-automation"), default="walking")
    fixture.add_argument("--mode", choices=MODES, default="full-public")
    fixture.add_argument(
        "--force",
        action="store_true",
        help="Refresh known fixture files while preserving immutable run copies.",
    )

    full = sub.add_parser("full", help="Collect public data, build baselines, and analyze.")
    add_common_project(full)
    full.add_argument("--query", action="append", default=[])
    full.add_argument("--period-days", type=int)
    full.add_argument("--limit", type=int, default=5)
    full.add_argument("--niche", default="generic")
    full.add_argument("--mode", choices=MODES, default="metadata-only")
    full.add_argument("--baseline-limit", type=int, default=20)
    full.add_argument("--timeout", type=float, default=20.0)

    return parser


def command_search(args: argparse.Namespace) -> None:
    ensure_project(args.project_root)
    extra: list[str] = []
    for query in args.query:
        extra += ["--query", query]
    extra += ["--limit-per-query", str(args.limit), "--command-timeout-sec", str(args.timeout),
              "--fallback-provider", "ytsearchdate", "--fallback-provider", "youtube_url",
              "--fallback-provider", "cache", "--continue-on-search-error"]
    if args.period_days:
        extra += ["--period-days", str(args.period_days)]
    if not args.include_watchlist:
        extra.append("--skip-watchlist-channels")
    run_module("yt_search", args.project_root, extra)


def command_analyze(args: argparse.Namespace) -> None:
    ensure_project(args.project_root)
    extra = [
        "--project-root", str(args.project_root.resolve()),
        "--niche-config", str(package_config(args.niche)),
        "--mode", args.mode,
        "--top-outliers", str(args.top),
        "--limit-per-channel", str(args.limit_per_channel),
    ]
    if args.analysis_at:
        extra += ["--analysis-at", args.analysis_at]
    if args.run_id:
        extra += ["--run-id", args.run_id]
    run_module("yt_breakout_analyzer", args.project_root, extra)


def command_fixture(args: argparse.Namespace) -> None:
    if args.project_root.exists() and any(args.project_root.iterdir()) and not args.force:
        raise SystemExit(
            f"Fixture target is not empty; rerun with --force or choose an empty directory: "
            f"{public_project_label(args.project_root)}"
        )
    args.project_root.mkdir(parents=True, exist_ok=True)
    run_module("yt_breakout_fixture", args.project_root, [
        "--project-root", str(args.project_root.resolve()), "--niche", args.niche,
        "--mode", args.mode, "--force",
    ])


def command_full(args: argparse.Namespace) -> None:
    command_search(argparse.Namespace(
        project_root=args.project_root, query=args.query, period_days=args.period_days,
        limit=args.limit, include_watchlist=True, timeout=args.timeout,
    ))
    run_module("yt_channel_baselines", args.project_root, [
        "--include-search-channels", "--limit-per-channel", str(args.baseline_limit),
        "--command-timeout-sec", str(args.timeout), "--continue-on-error",
    ])
    if args.mode in ("metadata+comments", "full-public"):
        run_module("yt_comments", args.project_root, ["--limit", str(args.limit), "--command-timeout-sec", str(args.timeout)])
    if args.mode == "full-public":
        run_module("yt_transcripts", args.project_root, ["--limit", str(args.limit)])
    if args.mode in ("metadata+visual", "full-public"):
        run_module("yt_thumbnails", args.project_root, ["--top", str(args.limit), "--timeout-sec", str(args.timeout)])
    command_analyze(argparse.Namespace(
        project_root=args.project_root, niche=args.niche, mode=args.mode, top=25,
        limit_per_channel=args.baseline_limit, analysis_at=None, run_id=None,
    ))


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "init":
        project_root = args.project_root.resolve()
        ensure_project(project_root, force=args.force)
        print(public_project_label(project_root))
    elif args.command == "search":
        command_search(args)
    elif args.command == "analyze":
        command_analyze(args)
    elif args.command == "fixture":
        command_fixture(args)
    elif args.command == "full":
        command_full(args)


if __name__ == "__main__":
    main()
