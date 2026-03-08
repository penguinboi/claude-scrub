# Contributing to claude-scrub

Thanks for your interest in contributing! Here's everything you need to get started.

## Development Setup

```bash
git clone https://github.com/penguinboi/claude-scrub.git
cd claude-scrub

# Install dev tools
pip install ruff pytest pre-commit

# Set up pre-commit hooks
pre-commit install

# Run tests
python3 -m pytest tests/ -v
```

That's it — zero dependencies beyond the dev tools above.

## Code Style

- **Ruff** enforces linting (E, F, W, I rules) and formatting
- Pre-commit hooks run ruff + the full test suite on every commit
- Target Python 3.8+ — no f-string walrus operators, no `match` statements
- This is a single-file CLI (`claude-scrub`) by design — don't split it into a package

## Making Changes

1. **Fork and branch** from `main`
2. **Write tests first** — we follow TDD. New features need tests; bug fixes need a regression test
3. **Keep changes small** — one concern per PR
4. **Run the full suite** before pushing: `python3 -m pytest tests/ -v`

## Pull Requests

- Give your PR a clear title describing what it does
- Explain *why* the change is needed, not just *what* changed
- All CI checks must pass (lint + tests on Python 3.8, 3.10, 3.12)

## Testing

- Tests live in `tests/test_claude_scrub.py`
- Use `unittest.TestCase` (matching existing style)
- Each test class gets its own `setUp`/`tearDown` with a fresh `tmpdir`
- Never mock the thing you're testing — mock dependencies, test real behavior
- Test output must be clean: no warnings, no errors

## Reporting Issues

- **Bugs**: Include steps to reproduce, expected vs actual behavior, Python version
- **Feature requests**: Describe the use case, not just the solution
- **False positives/negatives**: Include the pattern name and a (sanitized) example of the text that was misclassified

## Security Issues

See [SECURITY.md](SECURITY.md) — do not open public issues for vulnerabilities.
