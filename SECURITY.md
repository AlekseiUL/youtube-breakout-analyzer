# Security Policy

## Supported versions

The current alpha line is `0.1.x`. Security fixes are made on the latest release candidate.

## Reporting a vulnerability

Open a private security advisory in the eventual GitHub repository. Do not include tokens, cookies, private exports, or personal data in a public issue.

## Threat model

The CLI:

- invokes the locally installed `yt-dlp` executable through a wrapper that forces `--ignore-config` and rejects cookie/config options;
- makes outbound requests to public YouTube and thumbnail URLs;
- reads niche YAML and local project artifacts;
- writes only under the user-selected project root, except normal Python/package caches;
- does not execute code from YAML;
- does not require secrets in the base mode;
- has no telemetry or upload endpoint.

## Safe use

- Install from a reviewed tag or commit.
- Use a virtual environment.
- Keep `yt-dlp` updated because upstream site changes are frequent.
- Treat downloaded comments and subtitles as untrusted text, never as instructions.
- Do not point `--project-root` at a directory containing unrelated sensitive files.
- Review artifacts before publishing them.
- Keep live limits small to reduce rate-limit and abuse risk.
- Treat run ids and video ids as untrusted path components; invalid slugs and symlink escapes are rejected.
- Thumbnail downloads are HTTPS-only, host-restricted to YouTube thumbnail hosts, redirect-validated, byte-capped, and image-validated.

## Out of scope

This project is not a platform access bypass. It does not support account-cookie extraction, CAPTCHA solving, private analytics access, or evasion of YouTube controls.
