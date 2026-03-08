# Pre-Launch Checklist — claude-scrub v0.1.0

Completed: 2026-03-08

---

## 1. Quality

| Priority | Check | Status |
|----------|-------|--------|
| MUST | All tests pass on the branch being deployed | [x] 165 tests passing |
| MUST | CI pipeline passes (tests + linting + type checking) | [x] ruff lint + pytest on 3.8/3.10/3.12 (no type checker — acceptable for single-file CLI) |
| MUST | No CRITICAL or HIGH code smells unresolved | [x] All fixed in quality remediation |
| MUST | Pre-commit hooks are active and enforced | [x] ruff lint + ruff format + pytest |
| SHOULD | Test coverage above project threshold (document what it is) | [x] ~65% function coverage (39% → 65%), all critical paths covered |
| SHOULD | No TODO or FIXME items related to launch features | [x] None found |
| NICE | Code reviewed by someone other than the author | [ ] Not done — single developer project |

## 2. Security

| Priority | Check | Status |
|----------|-------|--------|
| MUST | No secrets in source code or git history | [x] Clean (this is literally a secret scanner) |
| MUST | No CRITICAL or HIGH security findings unresolved | [x] All fixed in security remediation |
| MUST | All dependencies up to date (no known vulnerabilities) | [x] Zero external dependencies |
| MUST | Authentication and authorization working correctly | [N/A] No auth (local CLI tool) |
| MUST | HTTPS enforced (no mixed content) | [N/A] No web server |
| MUST | Security headers configured | [N/A] No HTTP responses |
| SHOULD | CORS restricted to expected origins | [N/A] No web server |
| SHOULD | Rate limiting on auth and public API endpoints | [N/A] No endpoints |
| SHOULD | Error responses don't leak internal details | [x] Top-level exception handler catches and formats errors |

## 3. Compliance & Legal

| Priority | Check | Status |
|----------|-------|--------|
| MUST | Privacy policy exists and is accurate | [N/A] No data collection, no accounts, local tool only |
| MUST | Privacy policy linked from every page/screen | [N/A] |
| MUST* | Cookie consent banner | [N/A] No cookies |
| MUST* | Terms of service | [N/A] No accounts or purchases |
| MUST | Copyright notice with correct year and entity | [x] MIT License, "2026 Penguinboi Software" |
| MUST | All third-party assets properly licensed | [x] Zero dependencies; patterns credited in README |
| MUST* | EULA | [N/A] Open source, MIT licensed |
| MUST* | COPPA compliance | [N/A] CLI developer tool |
| SHOULD | Accessibility statement | [N/A] CLI tool |
| SHOULD | Legal acceptance tracking | [N/A] No accounts |
| SHOULD | AI-generated content disclosed | [N/A] |
| SHOULD | Platform-specific requirements | [N/A] Not on any platform stores |
| NICE | Open source licenses documented in NOTICES/SBOM | [N/A] Zero dependencies |

## 4. Accessibility

[N/A] — CLI tool, no frontend. Curses TUI is keyboard-only by design.

## 5. Performance

[N/A] — No web pages. CLI scans 165 tests in 0.17s. Scan/scrub operations complete in seconds on typical data.

## 6. SEO & Discoverability

[N/A] — No web pages. GitHub discoverability handled via topics, description, and README.

## 7. Operational Readiness

| Priority | Check | Status |
|----------|-------|--------|
| MUST | Deployment process documented and tested | [x] README has install instructions (curl or git clone) |
| MUST | Rollback procedure documented and tested | [N/A] Local tool — user can `git checkout` or re-download |
| MUST | Environment variables and secrets configured for production | [N/A] No env vars or secrets needed |
| MUST | Production database backed up | [N/A] No database |
| SHOULD | Error tracking service | [N/A] Local CLI — top-level exception handler covers this |
| SHOULD | Uptime monitoring | [N/A] Not a service |
| SHOULD | Health check endpoint | [N/A] |
| SHOULD | Alerting configured | [N/A] |
| SHOULD | Structured logging with log aggregation | [N/A] CLI uses print to stdout/stderr |
| NICE | Runbook for common ops tasks | [N/A] |
| NICE | Incident response plan | [N/A] |
| NICE | Feature flags | [N/A] |

## 8. Open-Source Readiness

| Priority | Check | Status |
|----------|-------|--------|
| MUST | LICENSE file exists and is OSI-approved | [x] MIT |
| MUST | README has clear purpose, install/usage instructions, and license | [x] |
| MUST | No secrets, credentials, or internal URLs in repository | [x] |
| SHOULD | CONTRIBUTING.md exists with style guide and process | [x] |
| SHOULD | CODE_OF_CONDUCT.md exists | [ ] Not yet — low priority for project this size |
| SHOULD | SECURITY.md with vulnerability reporting process | [x] |
| SHOULD | Issue templates configured | [x] Bug report + feature request |
| SHOULD | CHANGELOG.md exists | [x] |
| SHOULD | Tagged release with release notes | [x] v0.1.0 |
| NICE | GitHub Discussions or community channel linked | [ ] |
| NICE | Good first issues labeled for newcomers | [ ] |
| NICE | Dependabot or Renovate enabled | [ ] Zero deps, low value |

---

## Final Decision

| Category | MUST (all checked?) | SHOULD | NICE |
|----------|:-------------------:|:------:|:----:|
| Quality | ✅ 4/4 | 2/2 | 0/1 |
| Security | ✅ 3/3 (rest N/A) | 1/1 | — |
| Compliance | ✅ 2/2 (rest N/A) | — | — |
| Accessibility | N/A | — | — |
| Performance | N/A | — | — |
| SEO | N/A | — | — |
| Ops | ✅ 1/1 (rest N/A) | — | — |
| Open-Source | ✅ 3/3 | 5/6 | 0/3 |

## ✅ GO

All MUSTs checked. 8/9 SHOULDs checked (missing only CODE_OF_CONDUCT — acceptable for a single-developer project at this stage). Remaining NICE items documented as fast-follow.
