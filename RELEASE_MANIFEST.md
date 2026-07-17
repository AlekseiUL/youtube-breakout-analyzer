# Release Manifest — 0.1.0

## Artifact

- Repository: `youtube-breakout-analyzer`
- Release type: local public GitHub candidate
- Default state: not published
- License: MIT
- Python: 3.10+

## Included

- Python package and CLI
- public-data collectors
- channel baseline and breakout analyzer
- optional public enrichment layers
- three niche configs
- anonymous fixtures and tests
- standalone Hermes Agent Skill
- methodology, privacy, security, and contribution docs
- privacy and release-gate scripts
- GitHub Actions CI for Python 3.10–3.12

## Excluded

- private profiles, memory, agent identities, and team architecture
- internal paths and usernames
- real research lists and real customer/channel watchlists
- credentials, cookies, OAuth, API keys, and paid integrations
- private analytics and YouTube Studio data
- telemetry and upload services
- browser automation fallback

## Verified local candidate

- unit/integration suite: `14 passed, 4 subtests passed`;
- deterministic offline fixture: all required JSON/CSV/Markdown artifacts created and parsed;
- live neutral-topic smoke: 3 search candidates, 3 channel baselines built with 6 samples each, 21 analyzed records, 2 qualified channel-normalized outliers;
- small/established split: both branches populated in the live smoke;
- clean wheel install: `youtube-breakout 0.1.0` and installed-copy fixture passed;
- clean temporary `HERMES_HOME`: skill detected by `hermes skills list`;
- privacy scan: `PRIVACY_SCAN_OK`;
- generated fixture and live outputs: no `/Users/` home-path leakage;
- release gate: `RELEASE_GATE_OK`.

Live outputs are temporary verification artifacts and are not included in the repository.

## Required release gate

```bash
python -m pytest
python -m youtube_breakout.cli fixture --project-root /tmp/yba-release-fixture --force
python scripts/privacy_scan.py .
python scripts/release_gate.py
```

A public push requires a separate explicit user action. This repository candidate does not publish itself.
