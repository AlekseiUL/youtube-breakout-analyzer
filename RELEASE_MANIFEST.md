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

## Required local verification

The candidate is releasable only after `python scripts/release_gate.py` exits successfully with `RELEASE_GATE_OK`. A successful gate verifies:

- unit/integration/security-negative suite: `62 passed, 4 subtests passed`;
- deterministic offline fixture: all required JSON/CSV/Markdown artifacts created and privacy-scanned; core analysis JSON parsed and checked;
- wheel and sdist archives: built into a temporary directory and archive-checked;
- clean wheel install: installed CLI `youtube-breakout --version` and installed `init` smoke passed;
- standalone skill: root and `skills/youtube-breakout-analyzer/SKILL.md` consistency validated;
- privacy scan: `PRIVACY_SCAN_OK`;
- generated fixture outputs: no private absolute home/workspace/project-root path leakage;
- final success marker: `RELEASE_GATE_OK`.

Live YouTube collection is not part of the default release gate. It is a separate opt-in command because public platform availability is nondeterministic. The default gate may read from the configured Python package index for build isolation and while installing the built wheel and its declared runtime dependencies into a clean virtual environment.

## Required release gate

```bash
python scripts/release_gate.py
```

Optional live public collection smoke:

```bash
python scripts/release_gate.py --live-network-smoke
```

A public push requires a separate explicit user action. This repository candidate does not publish itself.
