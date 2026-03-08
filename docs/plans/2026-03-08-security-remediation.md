# Security Remediation Plan — 2026-03-08

## CRITICAL

### C1. Skip symlinks in discover_targets and scrub_targets
- **Files:** `claude-scrub` (discover_targets ~line 490, scrub_targets ~line 689)
- **Change:** Add `if f.is_symlink(): continue` before adding files to targets in discover_targets. Add `if filepath.is_symlink(): continue` before reading in scrub_targets.
- **Test:** Create symlink in test claude_dir, verify it's excluded from targets and not scrubbed
- **Verify:** `python3 -m pytest tests/ -x -q`

### C2. Add regex complexity checks for custom patterns
- **File:** `claude-scrub` (load_custom_patterns ~line 408)
- **Change:** Before `re.compile()`, reject patterns longer than 500 chars or containing nested quantifiers like `(x+)+`
- **Test:** Add test with a known ReDoS pattern, verify it's rejected with warning
- **Verify:** `python3 -m pytest tests/ -x -q`

### C3. Validate project_dir in launch_session
- **File:** `claude-scrub` (launch_session ~line 1320)
- **Change:** Use `Path(project_dir).resolve()` and verify `.is_dir()` on the resolved path
- **Test:** Manual verification (curses TUI function, hard to unit test)

## HIGH

### H1. Document secure_delete limitations
- **File:** `claude-scrub` (secure_delete ~line 298)
- **Change:** Add comment documenting that single-pass zero overwrite is best-effort, not forensically resistant on SSDs with wear-leveling
- **Test:** No code change needed, documentation only

### H2. Re-validate cached paths before scrub
- **File:** `claude-scrub` (cmd_scrub ~line 1710)
- **Change:** After loading cache, filter out paths that are symlinks or no longer regular files
- **Test:** Add test that creates cache, replaces file with symlink, verifies scrub skips it
- **Verify:** `python3 -m pytest tests/ -x -q`

### H3. Add download timeout and size limit
- **File:** `claude-scrub` (download_patterns_db ~line 447)
- **Change:** Set `socket.setdefaulttimeout(30)` before download. After download, check file size < 10MB.
- **Test:** Add test with mocked download that verifies timeout is set
- **Verify:** `python3 -m pytest tests/ -x -q`

## MEDIUM

### M1. Apply regex checks to downloaded patterns too
- **File:** `claude-scrub` (load_patterns_db ~line 430)
- **Change:** Reuse the same complexity check from C2 when loading downloaded patterns
- **Test:** Covered by C2 test if checks are in a shared function

### M2. Document entropy threshold limitations
- **File:** `claude-scrub` (entropy function ~line 374)
- **Change:** Add docstring noting Shannon entropy is a heuristic, not definitive
- **Test:** No code change needed, documentation only
