# Quality Audit — 2026-03-08

## Detected Stack

| Component | Value |
|-----------|-------|
| Language | Python (3.8+, zero external dependencies) |
| Project type | Single-file CLI tool |
| Test framework | pytest 9.0.2 |
| CI | GitHub Actions (Python 3.8, 3.10, 3.12) |
| Linter | None |
| Formatter | None |
| Type checker | None |
| Pre-commit hooks | None |

## Infrastructure: What Exists vs What's Missing

| Category | Status | Details |
|----------|--------|---------|
| Test runner | ✅ | pytest, 128 tests, 0.16s |
| CI pipeline | ✅ | GitHub Actions on push/PR, 3 Python versions |
| Test badge | ✅ | In README |
| Zero-dep design | ✅ | Intentional, reduces attack surface |
| Coverage tracking | ❌ | No coverage.py or pytest-cov |
| Linting | ❌ | No ruff, flake8, or pylint |
| Formatting | ❌ | No black or ruff format |
| Type checking | ❌ | No mypy/pyright, no type hints |
| Pre-commit hooks | ❌ | No .pre-commit-config.yaml |
| CI lint/format/type gates | ❌ | CI only runs pytest |
| pyproject.toml | ❌ | No packaging config |

## Function Test Coverage

**22/56 functions tested (39%)**

Tested: Core pattern matching, file discovery, scan/scrub, reporting, pattern loading, arg parsing, rotation list, stats.

Untested:
- **CLI handlers** (5): `cmd_scan`, `cmd_scrub`, `cmd_sessions`, `cmd_stats`, `main`
- **TUI/curses** (5): `interactive_mode`, `draw_header`, `draw_footer`, `pick_from_list`, `launch_session`
- **Session loading** (4): `load_all_sessions`, `load_indexed_sessions`, `extract_session_from_jsonl`, `load_all_patterns`
- **Utilities** (9): `format_bytes`, `format_date`, `parse_timestamp`, `truncate`, `project_path_from_dir_name`, `shorten_project`, `expand_project`, `clean_prompt`, `is_noise_prompt`
- **Cache** (2): `save_scan_cache`, `load_scan_cache`
- **Interactive** (2): `offer_rotation_list`, `prompt_save_rotation`
- **Other** (7): `filter_and_group`, `make_summary`, `parse_simple_toml`, `make_json_safe_regex`, `download_patterns_db`, `print_mode_output`, `secure_delete`

## Code Smell Findings

### CRITICAL

**1. `secure_delete()` silently swallows all errors** (line 223)
```python
except OSError:
    pass
```
A core security function fails silently. Caller has no idea if secrets remain on disk. Violates the "never silent fallbacks" rule.

**2. `download_patterns_db()` catches bare `Exception`** (line 375)
```python
except Exception as e:
    print(f"Error downloading patterns-db: {e}", file=sys.stderr)
    return False
```
Masks programming errors alongside network errors. Returns False, caller continues silently.

### HIGH

**3. TOCTOU race in `scrub_targets()`** (lines 603–608)
Between `read_text()` and `write_text()`, the file could change (e.g., Claude Code writing a new line). If `write_text()` fails partway (disk full), file is left partially scrubbed. Should use atomic writes.

**4. No type hints on any function** — 56 functions, zero annotations. Callers must read source to know `find_secrets()` returns 4-tuples. Refactoring is error-prone.

**5. `extract_session_from_jsonl()` reads entire file after finding first user message** (line 715) — Once `first_user_msg` is set, the loop continues reading potentially thousands of remaining lines. Needs early break.

### MEDIUM

**6. Global mutable `SECRET_PATTERNS` computed at import time** (line 118) — If mutated, affects all callers. Should be a function.

**7. `read_text(errors="replace")` silently mutates corrupt data** (line 603) — Invalid UTF-8 sequences replaced with U+FFFD, could miss secrets in binary regions.

**8. Cache format mismatch possible** — `load_scan_cache()` uses `.get()` with defaults (line 560), creating silent format drift between cached and live results.

**9. `--include` accepts any string silently** (line 933) — `--include=typo` is ignored without warning. Should validate against known categories.

**10. Curses rendering errors swallowed** (lines 1034, 1087, 1096) — `except curses.error: pass` masks rendering bugs beyond the expected bottom-right corner issue.

### LOW

**11.** `--days` accepts negative integers without error
**12.** Late stdlib imports (`urllib.request` inside function, line 369)
**13.** No test for entropy boundary (exactly 3.8 bits)
**14.** Cache invalidation after scrub not tested

### Clean Categories
- No circular dependencies
- No test interdependence (fresh tmpdir per test)
- No import-time side effects beyond pattern compilation
- No over-mocking in tests

## Statistics

| Metric | Value |
|--------|-------|
| Source lines | ~1,682 |
| Test lines | ~1,404 |
| Functions | 56 |
| Tests | 128 |
| Functions tested | 22 (39%) |
| CRITICAL findings | 2 |
| HIGH findings | 3 |
| MEDIUM findings | 5 |
| LOW findings | 4 |
