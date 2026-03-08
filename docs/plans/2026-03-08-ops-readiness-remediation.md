# Ops Readiness Remediation Plan — 2026-03-08

## HIGH

### O1. Add top-level exception handler
- **File:** `claude-scrub` (main function, line ~1852)
- **Change:** Wrap main() body in try/except that catches Exception, prints a clean one-line error to stderr, and exits with code 1. Optionally show traceback with `--debug` flag.
- **Test:** Add test that verifies main() doesn't crash with unhandled exception on bad input
- **Verify:** `python3 -m pytest tests/ -x -q`

## MEDIUM

### O2. Add --version flag
- **File:** `claude-scrub` (parse_args function)
- **Change:** Add `parser.add_argument("--version", action="version", version=f"claude-scrub {VERSION}")`
- **Test:** Add test that `parse_args(["--version"])` raises SystemExit (argparse behavior)
- **Verify:** `python3 claude-scrub --version`

### O3. Add CHANGELOG.md and tag first release
- **Files:** Create `CHANGELOG.md`, tag `v0.1.0`
- **Change:** Document current features as initial release
- **Verify:** `git tag -l`
