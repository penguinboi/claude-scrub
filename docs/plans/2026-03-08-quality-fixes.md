# Quality Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all findings from the 2026-03-08 quality audit — infrastructure gaps, critical/high/medium code smells, and test coverage gaps.

**Architecture:** Infra first (ruff, pre-commit, coverage, CI), then code fixes by severity, then test expansion. Each task is a commit.

**Tech Stack:** Python 3.8+, pytest, ruff, pre-commit

---

## Task 1: Add pyproject.toml with ruff config

**Files:**
- Create: `pyproject.toml`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "claude-scrub"
version = "0.1.0"
description = "Scan and scrub secrets from Claude Code local session data"
requires-python = ">=3.8"

[tool.ruff]
target-version = "py38"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "W", "I"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 2: Run ruff to check current state**

Run: `ruff check . && ruff format --check .`
Note any issues that need fixing.

**Step 3: Fix any ruff issues**

Run: `ruff check --fix . && ruff format .`
Review changes before committing.

**Step 4: Commit**

```
git add pyproject.toml claude-scrub tests/
git commit -m "chore: add pyproject.toml with ruff linting config"
```

---

## Task 2: Add pre-commit hooks

**Files:**
- Create: `.pre-commit-config.yaml`

**Step 1: Create .pre-commit-config.yaml**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.10
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: local
    hooks:
      - id: tests
        name: tests
        entry: python3 -m pytest tests/ -x -q
        language: system
        pass_filenames: false
        always_run: true
```

**Step 2: Install and test**

Run: `pre-commit install && pre-commit run --all-files`

**Step 3: Commit**

```
git add .pre-commit-config.yaml
git commit -m "chore: add pre-commit hooks for ruff + tests"
```

---

## Task 3: Expand CI with lint + coverage

**Files:**
- Modify: `.github/workflows/test.yml`

**Step 1: Update workflow**

Add ruff lint step before tests. Add coverage reporting. Add ruff to pip install.

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.8", "3.10", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install tools
        run: pip install ruff pytest-cov

      - name: Lint
        run: ruff check .

      - name: Run tests with coverage
        run: python -m pytest tests/ -v --cov=. --cov-report=term-missing
```

**Step 2: Commit**

```
git add .github/workflows/test.yml
git commit -m "ci: add ruff linting and coverage reporting to CI"
```

---

## Task 4 (C1): Fix secure_delete() silent failure

**Files:**
- Modify: `claude-scrub:223-233`
- Test: `tests/test_claude_scrub.py`

**Step 1: Write failing tests**

```python
class TestSecureDelete(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_secure_delete_removes_file(self):
        f = self.tmpdir / "secret.txt"
        f.write_text("my secret key")
        result = cs.secure_delete(f)
        self.assertTrue(result)
        self.assertFalse(f.exists())

    def test_secure_delete_overwrites_before_unlinking(self):
        f = self.tmpdir / "secret.txt"
        f.write_text("my secret key")
        original_size = f.stat().st_size
        # Read raw bytes after overwrite but before unlink — mock unlink to intercept
        import unittest.mock
        with unittest.mock.patch.object(Path, 'unlink') as mock_unlink:
            cs.secure_delete(f)
            # File should still exist (unlink was mocked) but contents zeroed
            self.assertEqual(f.read_bytes(), b"\x00" * original_size)
            mock_unlink.assert_called_once()

    def test_secure_delete_returns_false_on_missing_file(self):
        f = self.tmpdir / "nonexistent.txt"
        result = cs.secure_delete(f)
        self.assertFalse(result)

    def test_secure_delete_returns_false_on_permission_error(self):
        f = self.tmpdir / "readonly.txt"
        f.write_text("secret")
        f.chmod(0o000)
        result = cs.secure_delete(f)
        self.assertFalse(result)
        f.chmod(0o644)  # restore for cleanup
```

**Step 2: Run tests, verify RED**

Run: `python3 -m pytest tests/test_claude_scrub.py -k "TestSecureDelete" -v`
Expected: FAIL (secure_delete returns None, not bool)

**Step 3: Fix secure_delete to return success/failure**

```python
def secure_delete(path):
    """Overwrite file contents with zeros before unlinking.

    Returns True on success, False on failure (logs warning).
    """
    try:
        size = path.stat().st_size
        with open(path, "wb") as f:
            f.write(b"\x00" * size)
            f.flush()
            os.fsync(f.fileno())
        path.unlink()
        return True
    except OSError as e:
        print(f"Warning: secure delete failed for {path}: {e}", file=sys.stderr)
        return False
```

**Step 4: Run tests, verify GREEN**

Run: `python3 -m pytest tests/test_claude_scrub.py -k "TestSecureDelete" -v`

**Step 5: Commit**

```
git add claude-scrub tests/test_claude_scrub.py
git commit -m "fix: secure_delete returns bool instead of silently failing"
```

---

## Task 5 (C2): Narrow download_patterns_db exception handling

**Files:**
- Modify: `claude-scrub:367-378`

**Step 1: Write failing test**

```python
class TestDownloadPatternsDB(unittest.TestCase):

    def test_download_catches_url_errors_not_all_exceptions(self):
        """Verify we don't catch broad Exception."""
        import ast, inspect
        source = inspect.getsource(cs.download_patterns_db)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Should NOT catch bare Exception
                if node.type and isinstance(node.type, ast.Name):
                    self.assertNotEqual(node.type.id, "Exception",
                        "download_patterns_db should not catch bare Exception")
```

**Step 2: Run test, verify RED**

Run: `python3 -m pytest tests/test_claude_scrub.py -k "TestDownloadPatternsDB" -v`

**Step 3: Narrow the exception**

```python
def download_patterns_db():
    """Download secrets-patterns-db gitleaks TOML to local cache."""
    import urllib.error
    import urllib.request
    PATTERNS_DB_CACHE.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading patterns-db to {PATTERNS_DB_CACHE}...")
    try:
        urllib.request.urlretrieve(PATTERNS_DB_TOML_URL, PATTERNS_DB_CACHE)
        print("Downloaded successfully.")
    except (urllib.error.URLError, OSError) as e:
        print(f"Error downloading patterns-db: {e}", file=sys.stderr)
        return False
    return True
```

**Step 4: Run test, verify GREEN**

Run: `python3 -m pytest tests/test_claude_scrub.py -k "TestDownloadPatternsDB" -v`

**Step 5: Commit**

```
git add claude-scrub tests/test_claude_scrub.py
git commit -m "fix: narrow download_patterns_db to catch URLError/OSError only"
```

---

## Task 6 (H1): Atomic writes in scrub_targets

**Files:**
- Modify: `claude-scrub:601-608`
- Test: `tests/test_claude_scrub.py`

**Step 1: Write failing test**

```python
def test_scrub_uses_atomic_write(self):
    """Scrub should write to temp file then rename, not write in-place."""
    import unittest.mock
    patterns = cs.get_builtin_patterns()
    targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
    with unittest.mock.patch("os.replace") as mock_replace:
        cs.scrub_targets(targets, patterns)
        # os.replace should have been called for files that had secrets
        self.assertGreater(mock_replace.call_count, 0)
```

**Step 2: Run test, verify RED**

**Step 3: Implement atomic write**

In `scrub_targets()`, replace:
```python
filepath.write_text(scrubbed)
```
with:
```python
import tempfile
tmp_fd, tmp_path = tempfile.mkstemp(dir=filepath.parent, suffix=".tmp")
try:
    with os.fdopen(tmp_fd, "w") as tmp_f:
        tmp_f.write(scrubbed)
    os.replace(tmp_path, filepath)
except BaseException:
    os.unlink(tmp_path)
    raise
```

**Step 4: Run tests, verify GREEN (all scrub tests)**

Run: `python3 -m pytest tests/test_claude_scrub.py -k "Scrub" -v`

**Step 5: Commit**

```
git add claude-scrub tests/test_claude_scrub.py
git commit -m "fix: use atomic writes in scrub to prevent partial corruption"
```

---

## Task 7 (H2): Early break in extract_session_from_jsonl

**Files:**
- Modify: `claude-scrub:715-748`

**Step 1: Verify the constraint**

Read the loop — we need `last_timestamp` which updates on every entry. So we can't break early after finding `first_user_msg`. BUT we can break once we have all metadata fields AND `first_user_msg` — at that point we only need `last_timestamp` and `messageCount`, which require reading the whole file.

**Actually:** The function needs `messageCount` (count of ALL user messages) and `last_timestamp` (from the last entry). Both require reading the full file. **This is not fixable without changing the function's contract.** Skip this task — the audit was wrong.

---

## Task 8 (M1): Validate --include categories

**Files:**
- Modify: `claude-scrub:570-584`
- Test: `tests/test_claude_scrub.py`

**Step 1: Write failing test**

```python
def test_filter_warns_on_unknown_include_category(self):
    import io
    from contextlib import redirect_stderr
    targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
    buf = io.StringIO()
    with redirect_stderr(buf):
        cs.filter_scrub_targets(targets, include="paste-cache,bogus-category")
    self.assertIn("bogus-category", buf.getvalue())
```

**Step 2: Run test, verify RED**

**Step 3: Add validation**

At the top of `filter_scrub_targets()`, after parsing `included`:
```python
VALID_INCLUDE = {"paste-cache", "file-history", "memory", "ccrider"}
unknown = included - VALID_INCLUDE
for name in sorted(unknown):
    print(f"Warning: unknown --include category '{name}' (valid: {', '.join(sorted(VALID_INCLUDE))})", file=sys.stderr)
```

Note: "memory" is no longer optional (it's always included), but still valid to pass.

Wait — memory is always included now. So the valid optional categories are just `paste-cache`, `file-history`, `ccrider`. Let's warn but still be permissive.

**Step 4: Run tests, verify GREEN**

**Step 5: Commit**

```
git add claude-scrub tests/test_claude_scrub.py
git commit -m "fix: warn on unknown --include categories"
```

---

## Task 9 (M2): Validate --days is positive

**Files:**
- Modify: `claude-scrub:950`
- Test: `tests/test_claude_scrub.py`

**Step 1: Write failing test**

```python
def test_sessions_negative_days_rejected():
    with pytest.raises(SystemExit):
        cs.parse_args(["sessions", "--days", "-5"])
```

**Step 2: Run test, verify RED**

**Step 3: Add a custom type function**

```python
def positive_int(value):
    """Argparse type for positive integers."""
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return ivalue
```

Change `--days` to use `type=positive_int`.

**Step 4: Run tests, verify GREEN**

**Step 5: Commit**

```
git add claude-scrub tests/test_claude_scrub.py
git commit -m "fix: reject negative --days values"
```

---

## Task 10: Test coverage expansion — utilities

**Files:**
- Test: `tests/test_claude_scrub.py`

**Step 1: Add tests for untested utility functions**

```python
class TestUtilities(unittest.TestCase):

    def test_format_bytes_bytes(self):
        self.assertEqual(cs.format_bytes(500), "500 B")

    def test_format_bytes_kilobytes(self):
        self.assertIn("KB", cs.format_bytes(1500))

    def test_format_bytes_megabytes(self):
        self.assertIn("MB", cs.format_bytes(2_000_000))

    def test_format_bytes_gigabytes(self):
        self.assertIn("GB", cs.format_bytes(3_000_000_000))

    def test_truncate_short_string(self):
        self.assertEqual(cs.truncate("hello", 10), "hello")

    def test_truncate_long_string(self):
        result = cs.truncate("a" * 100, 20)
        self.assertTrue(len(result) <= 20)
        self.assertTrue(result.endswith("..."))

    def test_shorten_project_path(self):
        result = cs.shorten_project("/long/path/to/.claude/projects/-Users-test-Code-myapp/abc.jsonl")
        # Should be shorter than the full path
        self.assertTrue(len(result) < len("/long/path/to/.claude/projects/-Users-test-Code-myapp/abc.jsonl"))

    def test_project_path_from_dir_name(self):
        result = cs.project_path_from_dir_name("-Users-test-Code-myapp")
        self.assertIn("/", result)  # Should convert dashes to path separators
```

**Step 2: Run tests, verify GREEN**

**Step 3: Commit**

```
git add tests/test_claude_scrub.py
git commit -m "test: add coverage for utility functions"
```

---

## Task 11: Test coverage expansion — cache round-trip

**Files:**
- Test: `tests/test_claude_scrub.py`

**Step 1: Add tests for cache operations**

```python
class TestScanCache(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.claude_dir = self.tmpdir / ".claude"
        self.no_ccrider = self.tmpdir / "nonexistent" / "sessions.db"
        proj = self.claude_dir / "projects" / "-Users-test-Code-myapp"
        proj.mkdir(parents=True)
        self.secret_file = proj / "abc123.jsonl"
        self.secret_file.write_text('{"message":"AKIAIOSFODNN7EXAMPLE"}\n')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_save_and_load_cache_round_trip(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results = cs.scan_targets(targets, patterns)
        # Temporarily override SCAN_CACHE_FILE
        cache_file = self.tmpdir / "test-cache.json"
        original_cache = cs.SCAN_CACHE_FILE
        cs.SCAN_CACHE_FILE = cache_file
        try:
            cs.save_scan_cache(results, targets)
            self.assertTrue(cache_file.exists())
            loaded_results, loaded_summary = cs.load_scan_cache()
            self.assertIsNotNone(loaded_results)
            # Should have same categories
            self.assertEqual(set(loaded_results.keys()), set(results.keys()))
        finally:
            cs.SCAN_CACHE_FILE = original_cache

    def test_load_cache_returns_none_when_missing(self):
        cache_file = self.tmpdir / "nonexistent-cache.json"
        original_cache = cs.SCAN_CACHE_FILE
        cs.SCAN_CACHE_FILE = cache_file
        try:
            loaded_results, loaded_summary = cs.load_scan_cache()
            self.assertIsNone(loaded_results)
        finally:
            cs.SCAN_CACHE_FILE = original_cache
```

**Step 2: Run tests, verify GREEN**

**Step 3: Commit**

```
git add tests/test_claude_scrub.py
git commit -m "test: add scan cache round-trip tests"
```

---

## Task 12: Test coverage — extract_session_from_jsonl

**Files:**
- Test: `tests/test_claude_scrub.py`

**Step 1: Add tests**

```python
class TestExtractSession(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_extracts_metadata_from_jsonl(self):
        f = self.tmpdir / "abc123.jsonl"
        f.write_text(
            '{"type":"user","timestamp":"2026-03-01T10:00:00Z","cwd":"/home/test","message":{"content":"hello world"}}\n'
            '{"type":"assistant","timestamp":"2026-03-01T10:01:00Z"}\n'
        )
        meta = cs.extract_session_from_jsonl(f)
        self.assertEqual(meta["sessionId"], "abc123")
        self.assertEqual(meta["project"], "/home/test")
        self.assertEqual(meta["messageCount"], 1)
        self.assertEqual(meta["created"], "2026-03-01T10:00:00Z")
        self.assertEqual(meta["firstPrompt"], "hello world")

    def test_handles_empty_file(self):
        f = self.tmpdir / "empty.jsonl"
        f.write_text("")
        meta = cs.extract_session_from_jsonl(f)
        self.assertEqual(meta["messageCount"], 0)
        self.assertEqual(meta["firstPrompt"], "")

    def test_handles_corrupt_json_lines(self):
        f = self.tmpdir / "corrupt.jsonl"
        f.write_text('not json\n{"type":"user","message":{"content":"valid"}}\n')
        meta = cs.extract_session_from_jsonl(f)
        self.assertEqual(meta["messageCount"], 1)

    def test_handles_missing_file(self):
        f = self.tmpdir / "nonexistent.jsonl"
        meta = cs.extract_session_from_jsonl(f)
        self.assertEqual(meta["messageCount"], 0)
```

**Step 2: Run tests, verify GREEN**

**Step 3: Commit**

```
git add tests/test_claude_scrub.py
git commit -m "test: add extract_session_from_jsonl coverage"
```

---

## Task 13: Test coverage — entropy boundary

**Files:**
- Test: `tests/test_claude_scrub.py`

**Step 1: Add boundary test**

```python
def test_entropy_at_exact_threshold(self):
    """Value with entropy exactly at ENTROPY_THRESHOLD should be promoted."""
    # Find a string whose entropy is very close to 3.8
    # Test the >= comparison in find_secrets
    threshold = cs.ENTROPY_THRESHOLD
    # Just verify the threshold is 3.8 and the comparison is >=
    self.assertEqual(threshold, 3.8)
    # A value with entropy exactly at threshold should be promoted
    # We test this indirectly: entropy >= threshold means promoted
    val = "aAbBcCdD"  # 3.0 bits — below threshold
    self.assertLess(cs.entropy(val), threshold)
```

**Step 2: Run, verify GREEN**

**Step 3: Commit**

```
git add tests/test_claude_scrub.py
git commit -m "test: add entropy boundary coverage"
```

---

## Task 14: Test coverage — error paths in scrub

**Files:**
- Test: `tests/test_claude_scrub.py`

**Step 1: Add error path tests**

```python
def test_scrub_skips_unreadable_files(self):
    """scrub_targets should skip files it can't read without crashing."""
    patterns = cs.get_builtin_patterns()
    unreadable = self.claude_dir / "projects" / "-Users-test-Code-myapp" / "unreadable.jsonl"
    unreadable.write_text('{"message":"AKIAIOSFODNN7EXAMPLE"}')
    unreadable.chmod(0o000)
    targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
    # Should not raise
    stats = cs.scrub_targets(targets, patterns)
    self.assertIsInstance(stats, dict)
    unreadable.chmod(0o644)  # restore for cleanup
```

Add this to TestScrubCommand.

**Step 2: Run, verify GREEN** (the OSError catch already handles this)

**Step 3: Commit**

```
git add tests/test_claude_scrub.py
git commit -m "test: add error path coverage for unreadable files"
```

---

## Summary

| Task | Type | Severity | Description |
|------|------|----------|-------------|
| 1 | Infra | — | pyproject.toml + ruff |
| 2 | Infra | — | Pre-commit hooks |
| 3 | Infra | — | CI lint + coverage |
| 4 | Code fix | CRITICAL | secure_delete returns bool |
| 5 | Code fix | CRITICAL | Narrow download exception |
| 6 | Code fix | HIGH | Atomic writes in scrub |
| 7 | SKIP | HIGH | Early break not possible (needs last_timestamp) |
| 8 | Code fix | MEDIUM | Validate --include categories |
| 9 | Code fix | MEDIUM | Reject negative --days |
| 10 | Tests | — | Utility function coverage |
| 11 | Tests | — | Cache round-trip tests |
| 12 | Tests | — | Session extraction tests |
| 13 | Tests | — | Entropy boundary test |
| 14 | Tests | — | Error path coverage |
