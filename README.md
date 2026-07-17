# YouTube Breakout Analyzer

A local-first Python CLI for finding **channel-normalized YouTube breakout videos** from public signals.

It is not a popularity leaderboard. A video with 50,000 views can be more interesting than a video with 5,000,000 views when the first performs 20× above its channel baseline and the second performs near normal for its channel.

## What it does

1. Searches YouTube through public `yt-dlp` paths.
2. Collects public video and channel metadata.
3. Builds recent per-channel baselines.
4. Calculates channel-relative outlier multipliers.
5. Separates small-channel breakouts from established-channel breakouts.
6. Optionally analyzes public comments, subtitles, and thumbnail pixels.
7. Produces an evidence-led report, source ledger, content playbook, and `PATTERN_BANK`.

## What it does **not** do

- No YouTube API key in the base mode.
- No OAuth, account login, browser cookies, or YouTube Studio metrics.
- No paid API requirement.
- No hidden browser automation fallback.
- No inherited `yt-dlp` user config, cookie files, or browser-cookie options.
- No claim that an observed pattern caused performance.
- No promised access to comments, captions, or thumbnails when YouTube does not expose them.
- No demographic inference, face identification, or private-data enrichment.

> **Evidence boundary:** CTR, retention, traffic sources, revenue, and conversion for third-party videos are not publicly available. This tool analyzes open signals and statistical associations. It does not prove why a video succeeded and does not guarantee virality.

> Public availability is not guaranteed. YouTube can rate-limit, remove fields, change extraction behavior, or return incomplete data. The analyzer records those gaps instead of inventing values.

## Quickstart

Requirements:

- Python 3.10+
- network access for live collection
- `yt-dlp` (installed with the package)
- optional Pillow for local pixel metrics

```bash
git clone https://github.com/YOUR_ORG/youtube-breakout-analyzer.git
cd youtube-breakout-analyzer
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[visual]'
```

Create an analysis instance:

```bash
youtube-breakout init --project-root ./work/my-topic
```

Run a small public-data collection and analysis:

```bash
youtube-breakout full \
  --project-root ./work/my-topic \
  --query "urban gardening" \
  --period-days 90 \
  --limit 5 \
  --niche generic \
  --mode metadata-only
```

Run the deterministic offline fixture:

```bash
youtube-breakout fixture \
  --project-root /tmp/youtube-breakout-fixture \
  --niche walking \
  --force
```

## Commands

```text
youtube-breakout init      create a local project structure
youtube-breakout search    collect public search metadata
youtube-breakout analyze   analyze existing local artifacts
youtube-breakout fixture   generate and analyze anonymous offline fixtures
youtube-breakout full      run search → baselines → optional enrichments → analysis
```

Inspect exact options with:

```bash
youtube-breakout --help
youtube-breakout full --help
```

## Analysis modes

| Mode | Metadata | Public comments | Thumbnail pixels | Public subtitles |
|---|---:|---:|---:|---:|
| `metadata-only` | yes | no | no | no |
| `metadata+comments` | yes | best effort | no | no |
| `metadata+visual` | yes | no | best effort | no |
| `full-public` | yes | best effort | best effort | best effort |

Missing optional layers and missing public counts do not silently become zero. Reports use explicit states such as `NOT_REQUESTED`, `MISSING_*`, `NO_TRANSCRIPT:*`, or `visual_metrics_unavailable`; degraded visual artifacts do not receive visual evidence credit.

## Channel-normalized scoring

For a video $v$ on channel $c$:

```text
channel_outlier_multiplier = video_views / median(recent_channel_video_views)
```

Default interpretation:

| Multiplier | Label |
|---:|---|
| `< 5×` | below strong-outlier threshold |
| `5×–9.99×` | strong channel outlier |
| `10×–19.99×` | breakout |
| `≥ 20×` | extreme breakout |

A channel needs a minimum usable public-view baseline sample. If it does not have one, the tool emits `INSUFFICIENT_CHANNEL_BASELINE`; it does not pretend that the multiplier is reliable.

The ranking also records views/day, topic-relative velocity when available, comment rate, evidence coverage, and counterexamples. See [METHODOLOGY.md](METHODOLOGY.md).

## Output files

A run writes latest artifacts to `<project-root>/result/` and an immutable run copy under `result/breakout-runs/<run-id>/`:

- `breakout-analysis.json`
- `breakout-analysis.csv`
- `breakout-report.md`
- `content-playbook.md`
- `shooting-playbook.md` (compatibility alias)
- `PATTERN_BANK.json`
- `PATTERN_BANK.md`
- `source-ledger.json`
- `source-ledger.csv`
- `breakout-visual-manifest.json`
- `breakout-latest.json`

If the same run id already exists under `result/breakout-runs/`, the analyzer refuses to overwrite it. Run ids and video-id-derived paths must be simple slugs; absolute paths, parent traversal, separators, invalid characters, and symlink escapes are rejected.

## `PATTERN_BANK`

Each pattern contains:

- evidence;
- counterexamples;
- production hypothesis;
- confidence;
- known facts;
- unknowns;
- next controlled test;
- the warning `association, not proven cause`.

Patterns are generated only from qualified breakout examples. They are suggestions for experiments, not universal content laws.

## Niche configuration

Built-in examples:

- `generic`
- `walking`
- `ai-automation`

A niche YAML controls:

- breakout thresholds;
- minimum baseline samples;
- small-channel cutoff;
- inclusion keywords;
- metadata, comment, visual, and duration features.

Pass a custom file:

```bash
youtube-breakout analyze \
  --project-root ./work/my-topic \
  --niche ./my-niche.yaml \
  --mode metadata-only
```

## Watchlists

`youtube-breakout init` creates:

```text
watchlists/topics.yaml
watchlists/channels.yaml
```

You can add public channel URLs under `direct`, `adjacent`, or `global_signal`. No authentication is used. Treat watchlists as user-controlled inputs; do not commit private research lists unless you intend to publish them.

## Visual analysis limits

The optional visual layer downloads public thumbnails and computes local pixel metrics with Pillow:

- brightness;
- contrast;
- saturation;
- colorfulness proxy;
- edge-density proxy;
- simple descriptive labels.

It does **not** reliably detect faces, read thumbnail text, understand composition, or infer why a thumbnail performed. OCR and semantic vision are not included in the base package. Missing Pillow produces an explicit degraded status.

Thumbnail downloads are HTTPS-only, restricted to documented YouTube thumbnail hosts, validated across redirects, capped by size, and accepted only when the response has an image content type and supported image bytes. Unsafe URLs, unsafe redirects, oversized payloads, and non-images produce deterministic degraded/error rows.

## Public-data and platform limits

- Search results are not a complete index of YouTube.
- View and comment counts are point-in-time public values.
- Publication dates can be missing or ambiguous.
- Comments can be disabled, truncated, or rate-limited.
- Captions may be absent or unavailable.
- `yt-dlp` behavior depends on upstream YouTube changes.
- Repeated collection can trigger throttling; use small limits and respect the platform.

See [SECURITY.md](SECURITY.md) and [PRIVACY.md](PRIVACY.md).

## Hermes Agent Skill

A standalone skill is included at:

```text
skills/youtube-breakout-analyzer/SKILL.md
```

Install it into a profile-scoped Hermes skill directory:

```bash
mkdir -p "$HERMES_HOME/skills/youtube-breakout-analyzer"
cp SKILL.md "$HERMES_HOME/skills/youtube-breakout-analyzer/SKILL.md"
hermes skills list
```

The skill invokes the real installed `youtube-breakout` CLI; it does not simulate analysis in a prompt.

## Update, uninstall, and rollback

Update a source checkout and reinstall:

```bash
git pull --ff-only
python -m pip install -e '.[visual]'
python scripts/release_gate.py
```

Remove the Python package and optional skill:

```bash
python -m pip uninstall youtube-breakout-analyzer
rm -rf "$HERMES_HOME/skills/youtube-breakout-analyzer"
```

`rm -rf` is intentionally limited to the named skill directory. Review `$HERMES_HOME` before running it.

Rollback a Git checkout to a known release tag:

```bash
git switch --detach v0.1.0
python -m pip install --force-reinstall .
```

Analysis projects are separate directories. Package uninstall does not delete their `data/` or `result/` files.

## Troubleshooting

| Symptom | Check |
|---|---|
| `yt-dlp` extraction fails | Upgrade `yt-dlp`, retry with a small limit, and inspect explicit provider/error statuses. |
| Zero videos after search | Increase `--period-days`; the found public results may be older than the chosen window. |
| Channel baseline is insufficient | Raise `--baseline-limit` or collect a channel with at least the niche config's minimum sample. |
| Visual layer is degraded | Install `Pillow` with `pip install 'youtube-breakout-analyzer[visual]'`. |
| Comments or captions are missing | Treat the layer as unavailable; do not convert missing evidence to zero. |
| Skill is not listed | Confirm `SKILL.md` is under `$HERMES_HOME/skills/youtube-breakout-analyzer/`, then start a new Hermes session. |

## Development

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[test,visual]'
.venv/bin/python -m pytest
```

Release checks:

```bash
python scripts/privacy_scan.py .
python scripts/release_gate.py
```

`scripts/release_gate.py` does not collect from YouTube by default. It runs unit and security-negative tests, builds wheel and sdist archives in a temporary directory, checks the archives, installs the wheel and its declared runtime dependencies into a clean virtual environment, checks the installed dependency set, invokes the installed CLI, generates and scans offline fixtures, and validates the standalone skill copy. Build isolation and the dependency install may read from the configured Python package index. A best-effort live public collection smoke is separate and opt-in:

```bash
python scripts/release_gate.py --live-network-smoke
```

## Status

`0.1.0` is an alpha release candidate. The offline fixture path is deterministic. Live public collection is best effort and must remain transparent about degraded access.

## License

MIT. See [LICENSE](LICENSE).
