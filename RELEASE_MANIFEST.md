# Release Manifest — 0.1.1

## Artifact

- Repository: `youtube-breakout-analyzer`
- Release type: public GitHub release
- Canonical repository: `https://github.com/AlekseiUL/youtube-breakout-analyzer`
- License: MIT
- Python: 3.10+

## Included

- Python package and CLI
- public-data collectors
- channel baseline and breakout analyzer
- optional public enrichment layers
- three niche configs
- anonymous fixtures and tests
- complete English-first and Russian-second public documentation
- standalone Hermes Agent Skill
- methodology, privacy, security, and contribution docs
- privacy and release-gate scripts
- GitHub Actions CI for Python 3.10–3.12
- public README hero image with no EXIF, ICC profile, embedded comment, or private metadata

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

- unit/integration/security-negative suite passes;
- deterministic offline fixture: all required JSON/CSV/Markdown artifacts created and privacy-scanned; core analysis JSON parsed and checked;
- wheel and sdist archives: built into a temporary directory and archive-checked;
- clean wheel install: installed CLI `youtube-breakout --version`, `init`, and the full offline `fixture` smoke passed;
- standalone skill: root and `skills/youtube-breakout-analyzer/SKILL.md` consistency validated;
- privacy scan: `PRIVACY_SCAN_OK`;
- source and installed-package fixture outputs: no private absolute home/workspace/project-root path leakage;
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

Public publishing remains an explicit maintainer action; the package never publishes itself.
