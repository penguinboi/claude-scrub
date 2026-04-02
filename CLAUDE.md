# claude-scrub

CLI tool that scans and scrubs secrets from Claude Code local session data (`~/.claude/`). Single Python file, zero runtime dependencies, Python 3.8+ stdlib only.

**Repo:** github.com/penguinboi/claude-scrub (public, MIT license)

## Architecture

This is a single-file CLI by design — do not split it into a package.

```
claude-scrub              # The entire tool (executable Python script, no .py extension)
tests/test_claude_scrub.py  # All tests (165 tests, unittest.TestCase style)
pyproject.toml            # Ruff config, pytest config, project metadata
.pre-commit-config.yaml   # Ruff lint+format, pytest (runs on every commit)
.github/workflows/test.yml  # CI: lint + tests on Python 3.8, 3.10, 3.12
```

The script is imported in tests via `importlib.machinery.SourceFileLoader` since it has no `.py` extension.

## Subcommands

| Command | Description |
|---------|-------------|
| `scan` | Read-only audit of all Claude Code data files for secrets |
| `scrub` | Redact secrets in-place with `[REDACTED:<pattern-name>]` |
| `sessions` | Browse and resume past sessions (curses TUI or markdown output) |
| `stats` | Usage statistics (session counts, messages, disk usage) |

## Key Concepts

### Pattern Tiers
Matches are classified as **specific** (high-confidence, prefixed keys like `sk-ant-`, `AKIA`, `ghp_`) or **generic** (catch-all like `password=...`). Generic matches with high Shannon entropy (>=3.8 bits/char) are auto-promoted to specific. Default scrub only removes specific-tier matches; `--aggressive` includes generic.

### Scan Targets
Session files, indexes, history, paste cache, file history, memory files, and ccrider DB. Scan covers all; scrub defaults to sessions/indexes/history/memory (paste-cache, file-history, ccrider are opt-in via `--include`).

### Custom Patterns
Users add patterns in `~/.config/claude-scrub/config.toml` (TOML `[[patterns]]` with `name` and `regex`). Extended patterns via `--patterns-db` downloads gitleaks community format.

### Security Measures
- Symlink protection (skip symlinked files/directories)
- ReDoS prevention for custom/downloaded patterns (nested quantifier rejection, length limit)
- Atomic writes (temp file + `os.replace`) during scrub
- Secure delete (zero-overwrite + fsync) for cache files
- Download timeout and size limits for patterns-db
- JSON-safe regex rewriting (greedy `\S` matchers stop at JSON delimiters)

## Development

```bash
# Install dev tools
pip install ruff pytest pre-commit

# Set up hooks
pre-commit install

# Run tests
python3 -m pytest tests/ -v

# Lint
ruff check .
```

Pre-commit hooks run ruff (lint + format) and the full test suite. CI runs on Python 3.8, 3.10, 3.12.

### Test Style
- `unittest.TestCase` classes grouped by feature area (29 test classes)
- Each class with filesystem needs gets its own `setUp`/`tearDown` with a fresh `tmpdir`
- Tests import the script module as `cs` via importlib
- 165 tests covering argument parsing, pattern matching, file discovery, scan/scrub lifecycle, tier logic, entropy, Luhn validation, symlink protection, regex safety, caching, stats, rotation lists, and utilities

### Code Style
- Ruff with rules E, F, W, I; line length 120; target Python 3.8
- All code files start with two-line `# ABOUTME:` comments
- Single-file design — everything lives in `claude-scrub`

## Key Functions

| Function | Purpose |
|----------|---------|
| `get_builtin_patterns()` | Returns 44 named secret patterns with regex and tier |
| `find_secrets()` | Scans text for matches with deduplication and entropy promotion |
| `redact_secrets()` | Replaces matches with `[REDACTED:<name>]` |
| `discover_targets()` | Finds all Claude Code data files by category |
| `scan_targets()` | Scans discovered files with progress display |
| `scrub_targets()` | Atomic in-place redaction across files |
| `load_all_patterns()` | Merges built-in + custom + optional patterns-db |
| `entropy()` | Shannon entropy for tier promotion heuristic |
| `luhn_check()` | Credit card number validation |
| `parse_simple_toml()` | Minimal TOML parser (falls back when `tomllib` unavailable) |
| `interactive_mode()` | Curses-based two-level session picker |
| `gather_stats()` | Mines JSONL files for usage statistics |
| `build_rotation_list()` | Credential rotation checklist from scan results |

## Git Configuration

- **Name:** Skyler Lister Aley
- **Email:** skylerlisteraley@gmail.com
- **GitHub:** penguinboi
