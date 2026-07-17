# Contributing

## Setup

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[test,visual]'
```

## Before a pull request

```bash
.venv/bin/python -m pytest
.venv/bin/python -m youtube_breakout.cli fixture --project-root /tmp/yba-fixture --force
.venv/bin/python scripts/privacy_scan.py .
.venv/bin/python scripts/release_gate.py
```

## Rules

- Keep the base mode free of credentials, login, cookies, and paid services.
- Treat public availability as best effort.
- Record missing evidence explicitly; do not substitute guessed values.
- Keep fixtures synthetic and anonymous.
- Add tests for changed scoring or schema behavior.
- Do not describe an association as a proven cause.
- Do not add telemetry or uploads without an explicit design review and opt-in.
