# Security Audit — 2026-03-08

## Stack Summary

| Component | Value |
|-----------|-------|
| Language | Python 3.8+, zero external dependencies |
| Project type | Single-file CLI tool |
| Auth | None (local machine tool) |
| Network | Download only (patterns-db fetch), no server |
| Database | None |
| Subprocess | `pgrep` for process detection, `claude` for session launch |

## Findings by Severity

### CRITICAL

**C1. Symlink following in discover_targets and scrub_targets**
- **File:** `claude-scrub` lines 490-544 (discover_targets), 689-702 (scrub_targets)
- `pathlib` follows symlinks by default. If an attacker places a symlink in `~/.claude/projects/`, scan reads the target and scrub **overwrites** it with redacted content
- Also affects `scrub_targets()`: between read and write, `filepath` could be replaced with a symlink
- **Fix:** Check `is_symlink()` before adding to targets and before writing

**C2. ReDoS via custom patterns**
- **File:** `claude-scrub` lines 408-417 (load_custom_patterns)
- Custom patterns from `~/.config/claude-scrub/config.toml` are compiled without complexity checks
- A catastrophic backtracking regex (e.g., `(a+)+b`) causes scan to hang indefinitely
- **Fix:** Add regex length limit and nested quantifier check

**C3. Path traversal in launch_session**
- **File:** `claude-scrub` line 1334 (launch_session)
- `project_dir` from session JSON is passed to `os.chdir()` without validation
- Attacker who controls session JSON can redirect the working directory
- **Fix:** Resolve path and validate it's a real directory

### HIGH

**H1. Weak secure delete (single-pass zero overwrite)**
- **File:** `claude-scrub` lines 298-315
- Single zero-overwrite is insufficient on SSDs with wear-leveling
- **Fix:** Document limitation; optionally add multi-pass overwrite

**H2. Cache stores file paths without re-validation**
- **File:** `claude-scrub` lines 596-614 (save_scan_cache), 1710-1730 (cmd_scrub)
- Between cache creation and usage, files could be replaced with symlinks
- **Fix:** Re-validate paths are regular files before using cached results

**H3. No download timeout**
- **File:** `claude-scrub` lines 447-461 (download_patterns_db)
- `urllib.request.urlretrieve` has no timeout — could hang indefinitely
- No checksum verification of downloaded patterns
- **Fix:** Add socket timeout and file size limit

### MEDIUM

**M1. No validation of downloaded patterns-db content**
- Downloaded TOML patterns are loaded without ReDoS checks (same as C2 but for remote source)
- **Fix:** Apply same regex complexity checks to downloaded patterns

**M2. Entropy detection has known false positive/negative rates**
- Shannon entropy alone doesn't account for semantic meaning
- 3.8 threshold is heuristic — should be documented as such
- **Fix:** Document limitation in code comment

### LOW

**L1. Error messages may reveal filesystem structure** — Acceptable for local tool
**L2. Unknown --include categories warn but don't reject** — Already fixed (Task 7)
**L3. No regex match timeout** — Python less than 3.11 lacks regex timeout support
**L4. Session metadata reveals user paths** — Expected behavior for local tool

## Statistics

| Severity | Count |
|----------|-------|
| CRITICAL | 3 |
| HIGH | 3 |
| MEDIUM | 2 |
| LOW | 4 |

## Clean Categories

- No secrets in source code
- No eval/exec/unsafe deserialization
- All subprocess calls use list form (no shell=True)
- Cache excludes secret values (stores name + line + tier only)
- Zero external dependencies (no supply chain risk)
- Temp files created with 0o600 permissions
- No custom cryptography

## Risk Assessment

**Mitigating factor:** All attack vectors require write access to `~/.claude/` or `~/.config/claude-scrub/`. An attacker with that access has already compromised the user's account.

**Overall risk:** LOW for single-user systems, MEDIUM for shared systems.
