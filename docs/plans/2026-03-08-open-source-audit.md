# Open-Source Readiness Audit — 2026-03-08

## Project Detection

| Item | Status |
|------|--------|
| Public repo | ✅ GitHub (penguinboi/claude-scrub) |
| License | ✅ MIT (OSI-approved) |
| Language | Python 3.8+, zero dependencies |
| Type | CLI tool |
| Registry | ❌ Not on PyPI |

## Community Infrastructure

### Repository Essentials

| File | Status | Notes |
|------|--------|-------|
| README.md | ✅ | Clear purpose, install, usage, badges |
| LICENSE | ✅ | MIT, root of repo |
| CONTRIBUTING.md | ❌ | Missing |
| CODE_OF_CONDUCT.md | ❌ | Missing |
| SECURITY.md | ❌ | Missing |

### Issue & PR Management

| Item | Status | Notes |
|------|--------|-------|
| Issues enabled | ✅ | |
| Issue templates | ❌ | No bug report or feature request templates |
| PR template | ❌ | No pull request template |
| Labels | ❌ | No custom labels configured |
| Discussions | ❌ | Not enabled (fine for project this size) |

## Licensing & Legal

| Check | Status | Notes |
|-------|--------|-------|
| LICENSE file | ✅ | MIT, clear copyright |
| OSI-approved | ✅ | |
| Compatible with deps | ✅ | No dependencies |
| CLA/DCO | ⏭️ | Not needed at this scale |

## Versioning & Releases

| Check | Status | Notes |
|-------|--------|-------|
| Version in code | ✅ | `VERSION = "0.1.0"` |
| `--version` flag | ✅ | Works |
| Semantic versioning | ⚠️ | Used but not documented |
| CHANGELOG.md | ❌ | Missing |
| Tagged releases | ❌ | No git tags or GitHub releases |
| Release notes | ❌ | No releases exist |

## Contributor Experience

| Check | Status | Notes |
|-------|--------|-------|
| Clone-to-test path | ✅ | `git clone && pytest` — under 1 minute |
| Dev setup documented | ⚠️ | README has install but no dev/test instructions |
| Pre-commit hooks | ✅ | .pre-commit-config.yaml (ruff + tests) |
| Good first issues | ❌ | No labeled issues |
| Review process | ❌ | Not documented |

## Discoverability

| Check | Status | Notes |
|-------|--------|-------|
| Repo description | ⚠️ | "List and resume conversations" — outdated, doesn't mention secret scanning |
| Topics/tags | ❌ | None set |
| Website URL | ❌ | Not set |
| Badges | ✅ | Tests badge in README |
| Screenshots/demos | ❌ | No screenshots (CLI output examples serve this role partially) |

## Project Health

| Check | Status | Notes |
|-------|--------|-------|
| Recent commits | ✅ | Active today |
| CI on PRs | ✅ | GitHub Actions (lint + tests, 3 Python versions) |
| Dependabot/Renovate | ❌ | Not configured (less critical with zero deps) |
| Security policy | ❌ | No SECURITY.md |

## Findings by Severity

### HIGH

**OS1. Repo description is outdated**
- Currently: "List and resume your Claude Code conversations from the terminal"
- Should mention secret scanning/scrubbing — the primary purpose
- First thing potential users see on GitHub

**OS2. No SECURITY.md**
- A security tool without a vulnerability reporting policy is a bad look
- Users who find bugs in secret detection need a private channel

**OS3. No CONTRIBUTING.md**
- No contributor guide means PRs are guesswork
- Should document: how to run tests, code style, PR process

### MEDIUM

**OS4. No tagged releases or CHANGELOG**
- Users can't pin to a stable version
- No way to know what changed

**OS5. No repository topics**
- Not discoverable via GitHub search
- Should add: `claude`, `security`, `secrets`, `cli`, `python`

**OS6. No issue templates**
- Bug reports and feature requests lack structure
- Leads to low-quality issues

**OS7. No dev setup docs in README**
- README explains install/usage but not how to contribute/test

### LOW

**OS8. No PR template** — Would improve PR quality
**OS9. No CODE_OF_CONDUCT.md** — Standard community file
**OS10. Not on PyPI** — Limits install options (`pip install claude-scrub`)

## Statistics

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 4 |
| LOW | 3 |
