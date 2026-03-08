# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-03-08

First public release.

### Added
- **`scan` command** — Read-only audit of all Claude Code data files for secrets
- **`scrub` command** — Redact secrets in-place with confirmation prompt
- **`sessions` command** — List and resume Claude Code conversations (curses TUI)
- **`stats` command** — Usage statistics for Claude Code sessions
- **40+ secret patterns** — AI providers, cloud, payment, dev platforms, crypto material, credit cards, auth headers, generic catch-all
- **Pattern tiers** — Specific (high-confidence) and generic (heuristic) with entropy-based promotion
- **Credit card detection** — Regex + Luhn checksum validation
- **Custom patterns** — User-defined patterns via `~/.config/claude-scrub/config.toml`
- **secrets-patterns-db** — Optional integration with gitleaks community patterns (`--patterns-db`)
- **Memory file scanning** — Scans `projects/*/memory/*` for secrets
- **Rotation checklist** — `--rotation-list` generates a list of credentials to rotate (text or JSON)
- **Scan cache** — Results cached for 1 hour (no secret values stored)
- **Secure delete** — Zero-overwrite + fsync before unlinking cache files
- **Progress display** — Real-time scan progress with file counter, match tally, and ETA
- **Concurrent session warning** — Warns if Claude Code is running during scrub
- **`--aggressive` flag** — Also scrub generic/low-entropy matches
- **`--dry-run` flag** — Preview what would be scrubbed
- **`--include` flag** — Opt in to scrubbing paste-cache, file-history, ccrider

### Security
- Symlink protection in file discovery and scrub operations
- ReDoS prevention for custom and downloaded patterns
- Path traversal protection in session launcher
- Atomic writes in scrub (temp file + `os.replace`)
- Download timeout and file size limits for patterns-db
- Cache re-validates paths on load (skips symlinks and missing files)

### Infrastructure
- CI with ruff linting and test coverage on Python 3.8, 3.10, 3.12
- Pre-commit hooks (ruff lint, ruff format, pytest)
- 165 tests

[0.1.0]: https://github.com/penguinboi/claude-scrub/releases/tag/v0.1.0
