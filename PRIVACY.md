# Privacy

YouTube Breakout Analyzer is designed for local analysis of publicly exposed YouTube signals.

## Base-mode boundaries

The base workflow does not request or require:

- YouTube account login;
- OAuth;
- browser cookies;
- API keys;
- paid services;
- YouTube Studio or private creator analytics;
- private team files or private agent profiles.

## Data written locally

Depending on mode, a project directory can contain:

- public video/channel metadata;
- public comments, including public author names and URLs exposed by the extractor;
- public subtitles;
- public thumbnail images;
- local reports and derived features.

These files remain in the user-selected project directory. The package does not include telemetry or upload logic.

## User responsibility

Public data can still be personal data. Before sharing a project directory or report:

- review comment exports and public author identifiers;
- remove data not necessary for the stated research purpose;
- do not combine public records with private identity data;
- respect applicable law, platform terms, and deletion requests;
- do not commit user-specific watchlists unintentionally.

## Fixtures

Checked-in fixtures are synthetic and use invented channel names and video IDs. They contain no real comments or private research lists.

## Browser automation

The base package has no browser automation fallback. If a downstream fork adds one, it must be explicit, opt-in, documented, and must not use account cookies by default.
