# Quality Remediation Plan — 2026-03-08

## Infrastructure Tasks

### 1. Add ruff linting + formatting
- Create `pyproject.toml` with ruff config (select sensible defaults: E, F, W, I)
- Add `ruff check` and `ruff format --check` to CI workflow
- Run initial fix pass: `ruff check --fix && ruff format`
- **Test:** `ruff check . && ruff format --check .`

### 2. Add pre-commit hooks
- Create `.pre-commit-config.yaml` with ruff + pytest
- **Test:** `pre-commit run --all-files`

### 3. Add coverage tracking to CI
- Add `pytest-cov` to CI: `pip install pytest-cov && pytest --cov=. --cov-report=term-missing`
- Set coverage threshold (start at current %, ratchet up)
- **Test:** `python3 -m pytest --cov=. tests/`

### 4. Expand CI quality gates
- Add ruff lint step before test step
- Add coverage reporting step after test step
- **Test:** Push a branch and verify CI catches issues

## Code Fixes (by severity)

### CRITICAL

#### C1. Make `secure_delete()` report failures
- **File:** `claude-scrub` line 223
- **Change:** Return bool or raise; log warning on failure
- **Test:** Add tests for `secure_delete()` — success case, missing file, permission error

#### C2. Narrow `download_patterns_db()` exception handling
- **File:** `claude-scrub` line 375
- **Change:** Catch `(urllib.error.URLError, OSError)` instead of bare `Exception`
- **Test:** Add test for download failure (mock urllib or use invalid URL)

### HIGH

#### H1. Atomic writes in `scrub_targets()`
- **File:** `claude-scrub` line 608
- **Change:** Write to temp file in same directory, then `os.replace()` to atomically swap
- **Test:** Existing scrub tests should still pass; add test that verifies no partial writes

#### H2. Early break in `extract_session_from_jsonl()`
- **File:** `claude-scrub` line 715
- **Change:** After `first_user_msg` is found and all needed metadata is captured, break the loop
- **Verify first:** Check what metadata is still being collected after first_user_msg — may need last_timestamp from later entries (if so, can't break early)

#### H3. Add type hints to public functions (incremental)
- **Priority functions:** `find_secrets`, `redact_secrets`, `discover_targets`, `scan_targets`, `scrub_targets`, `filter_scrub_targets`, `build_rotation_list`
- **Test:** Run pyright/mypy after adding hints

### MEDIUM

#### M1. Validate `--include` categories
- **File:** `claude-scrub` line 933
- **Change:** After parsing, warn on unknown categories in `filter_scrub_targets()`
- **Test:** Add test that unknown include value produces warning

#### M2. Convert `SECRET_PATTERNS` global to function
- **File:** `claude-scrub` line 118
- **Change:** Make it a function call or lazy property
- **Verify first:** Check if any code depends on the module-level list being precomputed

#### M3. Log warning on `read_text(errors="replace")` substitutions
- **File:** `claude-scrub` line 603
- **Change:** Read as bytes first, attempt decode, warn if replacement chars appear
- **Verify first:** How common are non-UTF-8 session files?

### LOW

#### L1. Validate `--days` is positive
- **File:** `claude-scrub` line 950
- **Change:** `type=int, choices=range(1, 3651)` or manual validation
- **Test:** Add argparse test for negative days

#### L2. Add entropy boundary test
- **File:** `tests/test_claude_scrub.py`
- **Change:** Test a value with entropy exactly at 3.8 threshold
- **Test:** Self-verifying

## Test Coverage Expansion

### Priority 1: CLI handlers
- Test `cmd_scan`, `cmd_scrub`, `cmd_stats` with mocked CLAUDE_DIR and argv
- Capture stdout, verify expected output

### Priority 2: Session loading
- Test `extract_session_from_jsonl` with various JSONL formats
- Test `load_scan_cache` / `save_scan_cache` round-trip
- Test `load_all_patterns` with and without patterns-db

### Priority 3: Utility functions
- Test `format_bytes`, `format_date`, `truncate`, `shorten_project`
- These are simple but untested

### Priority 4: Error paths
- Test scrub with unreadable file (permission denied)
- Test scan with corrupt JSONL
- Test download failure for patterns-db
