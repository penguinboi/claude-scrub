# claude-scrub Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the existing `claude-sessions` script into `claude-scrub` — a CLI tool that scans and scrubs secrets from Claude Code's local data, with session listing as a secondary feature.

**Architecture:** Single Python file with argparse subcommands (scan, scrub, sessions). Pattern engine with named patterns shared across commands. File discovery layer abstracts target types. Zero dependencies beyond Python 3.6+ stdlib.

**Tech Stack:** Python 3.6+ stdlib only (argparse, re, json, pathlib, glob, tempfile, unittest, tomllib/fallback)

---

### Task 1: Test infrastructure and CLI skeleton

**Files:**
- Create: `tests/test_claude_scrub.py`
- Rename: `claude-sessions` → `claude-scrub`

**Step 1: Write the failing test for CLI entry point**

Create `tests/test_claude_scrub.py`:

```python
#!/usr/bin/env python3
# ABOUTME: Tests for claude-scrub CLI tool.
# ABOUTME: Uses unittest with temporary directories to simulate Claude Code data.

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Load claude-scrub as a module (it has no .py extension)
SCRIPT_PATH = Path(__file__).parent.parent / "claude-scrub"
spec = importlib.util.spec_from_file_location("claude_scrub", SCRIPT_PATH)
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)


class TestCLIParsing(unittest.TestCase):
    """Test argparse subcommand routing."""

    def test_scan_subcommand_parses(self):
        args = cs.parse_args(["scan"])
        self.assertEqual(args.command, "scan")

    def test_scrub_subcommand_parses(self):
        args = cs.parse_args(["scrub"])
        self.assertEqual(args.command, "scrub")

    def test_sessions_subcommand_parses(self):
        args = cs.parse_args(["sessions"])
        self.assertEqual(args.command, "sessions")

    def test_scan_verbose_flag(self):
        args = cs.parse_args(["scan", "--verbose"])
        self.assertTrue(args.verbose)

    def test_scan_patterns_db_flag(self):
        args = cs.parse_args(["scan", "--patterns-db"])
        self.assertTrue(args.patterns_db)

    def test_scrub_yes_flag(self):
        args = cs.parse_args(["scrub", "--yes"])
        self.assertTrue(args.yes)

    def test_scrub_include_flag(self):
        args = cs.parse_args(["scrub", "--include", "paste-cache,file-history"])
        self.assertEqual(args.include, "paste-cache,file-history")

    def test_sessions_latest_flag(self):
        args = cs.parse_args(["sessions", "--latest"])
        self.assertTrue(args.latest)

    def test_sessions_days_flag(self):
        args = cs.parse_args(["sessions", "--days", "7"])
        self.assertEqual(args.days, 7)

    def test_no_subcommand_shows_help(self):
        """Running with no subcommand should exit with error."""
        with self.assertRaises(SystemExit):
            cs.parse_args([])


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 tests/test_claude_scrub.py 2>&1 | head -20`
Expected: FAIL — `claude-scrub` file doesn't exist yet / `parse_args` doesn't accept list args

**Step 3: Rename file and implement CLI skeleton**

Rename `claude-sessions` to `claude-scrub` and replace the `parse_args` function with argparse subcommands. Keep ALL existing code intact — only replace the argument parsing section and the `main()` dispatch.

Replace the `parse_args` function (lines 381-429) with:

```python
def parse_args(argv=None):
    """Parse CLI arguments using argparse subcommands."""
    parser = argparse.ArgumentParser(
        prog="claude-scrub",
        description="Scan and scrub secrets from Claude Code session data.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    # --- scan ---
    scan_parser = subparsers.add_parser("scan", help="Audit Claude Code data for secrets (read-only)")
    scan_parser.add_argument("-v", "--verbose", action="store_true", help="Show per-file, per-line detail")
    scan_parser.add_argument("--patterns-db", action="store_true", help="Use secrets-patterns-db (1600+ patterns)")

    # --- scrub ---
    scrub_parser = subparsers.add_parser("scrub", help="Remove secrets from Claude Code data files")
    scrub_parser.add_argument("-v", "--verbose", action="store_true", help="Show per-file detail")
    scrub_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    scrub_parser.add_argument("--patterns-db", action="store_true", help="Use secrets-patterns-db (1600+ patterns)")
    scrub_parser.add_argument("--include", type=str, default="", help="Extra targets: paste-cache,file-history,ccrider")

    # --- sessions ---
    sess_parser = subparsers.add_parser("sessions", help="List and resume Claude Code sessions")
    sess_parser.add_argument("--latest", action="store_true", help="Only show most recent session per project")
    sess_parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"Days to look back (default: {DEFAULT_DAYS})")
    sess_parser.add_argument("--all", action="store_true", help="Show all sessions")
    sess_parser.add_argument("--min-msgs", type=int, default=MIN_MESSAGES, help=f"Min messages (default: {MIN_MESSAGES})")
    sess_parser.add_argument("--print", dest="print_mode", action="store_true", help="Output markdown instead of interactive picker")
    sess_parser.add_argument("-o", type=str, default=None, metavar="FILE", help="Write markdown to FILE")

    return parser.parse_args(argv)
```

Add `import argparse` to the imports at the top.

Update `main()` to dispatch based on `args.command`:

```python
def main():
    args = parse_args()

    if args.command == "sessions":
        cmd_sessions(args)
    elif args.command == "scan":
        cmd_scan(args)
    elif args.command == "scrub":
        cmd_scrub(args)


def cmd_sessions(args):
    """Run the sessions listing command."""
    if args.o:
        args.print_mode = True

    sessions = load_all_sessions()
    by_project = filter_and_group(sessions, args.days, args.all, args.min_msgs)

    if args.print_mode or not sys.stdout.isatty():
        print_mode_output(by_project, args.days, args.all, args.latest, args.o)
        return

    selected = curses.wrapper(lambda stdscr: interactive_mode(stdscr, by_project))
    if selected:
        launch_session(selected)


def cmd_scan(args):
    """Placeholder for scan command."""
    print("scan command not yet implemented")


def cmd_scrub(args):
    """Placeholder for scrub command."""
    print("scrub command not yet implemented")
```

Remove the old `parse_args` function entirely. Remove the old `main` function.

**Step 4: Run test to verify it passes**

Run: `python3 tests/test_claude_scrub.py -v`
Expected: All 10 tests PASS

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git rm claude-sessions
git commit -m "refactor: rename to claude-scrub with argparse subcommands

Rename claude-sessions to claude-scrub. Replace manual arg parsing
with argparse subcommands: scan, scrub, sessions. Add test
infrastructure. Existing sessions functionality preserved under
the sessions subcommand."
```

---

### Task 2: Named pattern engine

**Files:**
- Modify: `claude-scrub` (SECRET_PATTERNS section, lines ~41-131)
- Modify: `tests/test_claude_scrub.py`

Currently SECRET_PATTERNS is a list of bare compiled regexes. We need named patterns so scan/scrub can report _which_ pattern matched.

**Step 1: Write the failing tests**

Add to `tests/test_claude_scrub.py`:

```python
class TestPatternEngine(unittest.TestCase):
    """Test the named pattern engine."""

    def test_builtin_patterns_are_named(self):
        """Every built-in pattern must have a name and compiled regex."""
        patterns = cs.get_builtin_patterns()
        self.assertGreater(len(patterns), 30)
        for p in patterns:
            self.assertIn("name", p)
            self.assertIn("regex", p)
            self.assertIsNotNone(p["regex"].pattern)

    def test_find_secrets_returns_matches_with_names(self):
        """find_secrets should return list of (pattern_name, match_text, line_num)."""
        text = "my key is sk-ant-api03-AAAAABBBBCCCCDDDDEEEE1234567890abcdef"
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        self.assertGreater(len(matches), 0)
        name, match_text, line_num = matches[0]
        self.assertIsInstance(name, str)
        self.assertIn("sk-ant-api03", match_text)
        self.assertEqual(line_num, 1)

    def test_find_secrets_reports_line_numbers(self):
        """Secrets on different lines should have correct line numbers."""
        text = "line one\nAKIAIOSFODNN7EXAMPLE\nline three\nsk_live_abc1234567890"
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        lines = {m[2] for m in matches}
        self.assertIn(2, lines)  # AWS key on line 2
        self.assertIn(4, lines)  # Stripe key on line 4

    def test_find_secrets_empty_text(self):
        """No secrets in clean text."""
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets("hello world\nno secrets here", patterns)
        self.assertEqual(len(matches), 0)

    def test_redact_secrets_replaces_with_pattern_name(self):
        """redact_secrets should replace matches with [REDACTED:<name>]."""
        text = "key is AKIAIOSFODNN7EXAMPLE"
        patterns = cs.get_builtin_patterns()
        result = cs.redact_secrets(text, patterns)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", result)
        self.assertIn("[REDACTED:", result)

    def test_scrub_secrets_still_works(self):
        """Existing scrub_secrets function should still work for sessions output."""
        text = "token: sk-ant-api03-AAAAABBBBCCCCDDDDEEEE1234567890abcdef"
        result = cs.scrub_secrets(text)
        self.assertNotIn("sk-ant-api03", result)
        self.assertIn("[REDACTED]", result)
```

**Step 2: Run tests to verify they fail**

Run: `python3 tests/test_claude_scrub.py TestPatternEngine -v`
Expected: FAIL — `get_builtin_patterns`, `find_secrets`, `redact_secrets` don't exist

**Step 3: Implement named pattern engine**

Replace the `SECRET_PATTERNS` list (lines ~41-131) with a `get_builtin_patterns()` function that returns a list of dicts `{"name": str, "regex": compiled_regex}`:

```python
def get_builtin_patterns():
    """Return built-in secret patterns as a list of {"name": str, "regex": Pattern}."""
    raw = [
        # --- AI providers ---
        ("Anthropic API Key", r"sk-ant-api\d{2}-[A-Za-z0-9_-]{20,}"),
        ("Anthropic Admin Key", r"sk-ant-admin\d{2}-[A-Za-z0-9_-]{20,}"),
        ("OpenAI Project Key", r"sk-proj-[A-Za-z0-9_-]{20,}"),
        ("OpenAI API Key", r"sk-[A-Za-z0-9]{20,}"),
        # --- Cloud providers ---
        ("AWS Access Key", r"(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}"),
        ("AWS Secret Key Assignment", r"(?:aws_secret_access_key|secret_access_key)\s*[:=]\s*\S+"),
        ("Amazon MWS Token", r"amzn\.mws\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
        ("Google API Key", r"AIza[0-9A-Za-z\-_]{35}"),
        ("Google OAuth Token", r"ya29\.[0-9A-Za-z\-_]+"),
        ("Google OAuth Client ID", r"[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com"),
        ("Azure AD Client Secret", r"[a-zA-Z0-9_~.]{3}\dQ~[a-zA-Z0-9_~.-]{31,34}"),
        # --- Payment ---
        ("Stripe Key", r"[sr]k_(?:test|live|prod)_[a-zA-Z0-9]{10,99}"),
        ("Square Access Token", r"sq0atp-[0-9A-Za-z\-_]{22}"),
        ("Square OAuth Secret", r"sq0csp-[0-9A-Za-z\-_]{43}"),
        ("PayPal Braintree Token", r"access_token\$production\$[0-9a-z]{16}\$[0-9a-f]{32}"),
        # --- Communication ---
        ("Slack Token", r"xox[pboa]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*"),
        ("Slack Webhook", r"https://hooks\.slack\.com/services/T[a-zA-Z0-9_]{8}/B[a-zA-Z0-9_]{8}/[a-zA-Z0-9_]{24}"),
        ("Discord Token", r"(?:discord|bot)[\w.-]{0,20}[\s:=]+['\"]?[A-Za-z0-9._-]{50,}"),
        ("Twilio API Key", r"SK[0-9a-fA-F]{32}"),
        ("SendGrid Key", r"SG\.[a-zA-Z0-9=_\-.]{66}"),
        ("Mailchimp Key", r"[0-9a-f]{32}-us[0-9]{1,2}"),
        ("Mailgun Key", r"key-[0-9a-zA-Z]{32}"),
        # --- Dev platforms ---
        ("GitHub Token", r"gh[pousr]_[A-Za-z0-9_]{20,}"),
        ("GitLab Token", r"gl(?:pat|ptt|rt)-[A-Za-z0-9_-]{20,}"),
        ("npm Token", r"npm_[a-z0-9]{36}"),
        ("PyPI Token", r"pypi-[A-Za-z0-9_-]{50,}"),
        ("Shopify Token", r"shpat_[a-fA-F0-9]{32}"),
        ("Heroku API Key", r"(?:heroku)[\w.-]{0,20}[\s:=]+['\"]?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
        ("Notion Token", r"ntn_[0-9]{11}[A-Za-z0-9]{32,}"),
        ("Postman Token", r"PMAK-[a-f0-9]{24}-[a-f0-9]{34}"),
        ("Datadog Key", r"(?:datadog|dd)[\w.-]{0,20}[\s:=]+['\"]?[a-z0-9]{32,40}"),
        ("Vercel Token", r"(?:vercel)[\w.-]{0,20}[\s:=]+['\"]?[A-Za-z0-9]{24,}"),
        # --- Social ---
        ("Facebook Token", r"EAACEdEose0cBA[0-9A-Za-z]+"),
        ("Twitch Token", r"(?:twitch)[\w.-]{0,20}[\s:=]+['\"]?[a-z0-9]{30,}"),
        # --- Crypto ---
        ("Private Key", r"-----BEGIN[A-Z ]* PRIVATE KEY[A-Z ]*-----"),
        ("PGP Private Key", r"-----BEGIN PGP PRIVATE KEY BLOCK-----"),
        ("JWT Token", r"\bey[a-zA-Z0-9]{17,}\.ey[a-zA-Z0-9/\\_-]{17,}\."),
        # --- Generic ---
        ("Bearer Token", r"Bearer\s+[A-Za-z0-9._-]{20,}"),
        ("Authorization Header", r"Authorization:\s*\S+"),
        ("Generic Secret Assignment", r"(?:key|token|secret|password|credential|passwd|api_key|apikey)\s*[:=]\s*\S{8,}"),
        ("Password in URL", r"://[^@\s]+:[^@\s]+@"),
        ("Cloudinary URL", r"cloudinary://[^\s]+"),
    ]

    # Patterns with case-insensitive matching
    case_insensitive = {
        "AWS Secret Key Assignment", "Discord Token", "Heroku API Key",
        "Datadog Key", "Vercel Token", "Twitch Token", "Bearer Token",
        "Authorization Header", "Generic Secret Assignment",
    }

    patterns = []
    for name, regex in raw:
        flags = re.IGNORECASE if name in case_insensitive else 0
        patterns.append({"name": name, "regex": re.compile(regex, flags)})

    return patterns


# Keep compiled list for backward compat with scrub_secrets() in sessions output
SECRET_PATTERNS = [p["regex"] for p in get_builtin_patterns()]


def find_secrets(text, patterns):
    """Find all secrets in text. Returns list of (pattern_name, match_text, line_number)."""
    results = []
    lines = text.split("\n")
    for line_num, line in enumerate(lines, 1):
        for p in patterns:
            for match in p["regex"].finditer(line):
                results.append((p["name"], match.group(), line_num))
    return results


def redact_secrets(text, patterns):
    """Replace all secrets in text with [REDACTED:<pattern_name>]."""
    for p in patterns:
        text = p["regex"].sub(f"[REDACTED:{p['name']}]", text)
    return text
```

**Step 4: Run tests to verify they pass**

Run: `python3 tests/test_claude_scrub.py TestPatternEngine -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: named pattern engine for scan/scrub reporting

Convert anonymous SECRET_PATTERNS to named patterns via
get_builtin_patterns(). Add find_secrets() for line-level
detection and redact_secrets() for replacement. Keep backward-
compat SECRET_PATTERNS list for sessions output scrubbing."
```

---

### Task 3: File discovery

**Files:**
- Modify: `claude-scrub`
- Modify: `tests/test_claude_scrub.py`

Build the layer that finds all Claude Code data files, categorized by target type.

**Step 1: Write the failing tests**

Add to `tests/test_claude_scrub.py`:

```python
class TestFileDiscovery(unittest.TestCase):
    """Test discovery of Claude Code data files."""

    def setUp(self):
        """Create a fake ~/.claude directory structure."""
        self.tmpdir = tempfile.mkdtemp()
        self.claude_dir = Path(self.tmpdir) / ".claude"

        # Create session files
        proj = self.claude_dir / "projects" / "-Users-test-Code-myapp"
        proj.mkdir(parents=True)
        (proj / "abc123.jsonl").write_text('{"type":"user"}\n')
        (proj / "def456.jsonl").write_text('{"type":"user"}\n')
        (proj / "sessions-index.json").write_text('{"entries":[]}')

        # Create history
        (self.claude_dir / "history.jsonl").write_text('{"prompt":"hello"}\n')

        # Create paste cache
        paste = self.claude_dir / "paste-cache"
        paste.mkdir()
        (paste / "paste1.txt").write_text("some pasted content")

        # Create file history
        fh = self.claude_dir / "file-history"
        fh.mkdir()
        (fh / "snapshot1.txt").write_text("some code")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_discover_returns_all_categories(self):
        targets = cs.discover_targets(self.claude_dir)
        self.assertIn("sessions", targets)
        self.assertIn("indexes", targets)
        self.assertIn("history", targets)
        self.assertIn("paste_cache", targets)
        self.assertIn("file_history", targets)

    def test_discover_finds_session_jsonl_files(self):
        targets = cs.discover_targets(self.claude_dir)
        self.assertEqual(len(targets["sessions"]), 2)

    def test_discover_finds_index_files(self):
        targets = cs.discover_targets(self.claude_dir)
        self.assertEqual(len(targets["indexes"]), 1)

    def test_discover_finds_history(self):
        targets = cs.discover_targets(self.claude_dir)
        self.assertEqual(len(targets["history"]), 1)

    def test_discover_finds_paste_cache(self):
        targets = cs.discover_targets(self.claude_dir)
        self.assertEqual(len(targets["paste_cache"]), 1)

    def test_discover_finds_file_history(self):
        targets = cs.discover_targets(self.claude_dir)
        self.assertEqual(len(targets["file_history"]), 1)

    def test_discover_handles_missing_dirs(self):
        """Should not crash if some directories don't exist."""
        empty = Path(self.tmpdir) / "empty-claude"
        empty.mkdir()
        targets = cs.discover_targets(empty)
        for category in targets.values():
            self.assertEqual(len(category), 0)

    def test_discover_finds_ccrider_db(self):
        """Should find ccrider DB if it exists."""
        ccrider_dir = Path(self.tmpdir) / ".config" / "ccrider"
        ccrider_dir.mkdir(parents=True)
        db = ccrider_dir / "sessions.db"
        db.write_text("fake db")
        targets = cs.discover_targets(self.claude_dir, ccrider_db=db)
        self.assertEqual(len(targets["ccrider"]), 1)
```

**Step 2: Run tests to verify they fail**

Run: `python3 tests/test_claude_scrub.py TestFileDiscovery -v`
Expected: FAIL — `discover_targets` doesn't exist

**Step 3: Implement file discovery**

Add to `claude-scrub`:

```python
def discover_targets(claude_dir, ccrider_db=None):
    """Discover all Claude Code data files, categorized by type.

    Returns dict with keys: sessions, indexes, history, paste_cache, file_history, ccrider
    Each value is a list of Path objects.
    """
    targets = {
        "sessions": [],
        "indexes": [],
        "history": [],
        "paste_cache": [],
        "file_history": [],
        "ccrider": [],
    }

    projects_dir = claude_dir / "projects"
    if projects_dir.is_dir():
        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            for f in project_dir.iterdir():
                if f.suffix == ".jsonl" and f.is_file():
                    targets["sessions"].append(f)
                elif f.name == "sessions-index.json" and f.is_file():
                    targets["indexes"].append(f)

    history = claude_dir / "history.jsonl"
    if history.is_file():
        targets["history"].append(history)

    paste_dir = claude_dir / "paste-cache"
    if paste_dir.is_dir():
        for f in paste_dir.iterdir():
            if f.is_file():
                targets["paste_cache"].append(f)

    fh_dir = claude_dir / "file-history"
    if fh_dir.is_dir():
        for f in fh_dir.iterdir():
            if f.is_file():
                targets["file_history"].append(f)

    if ccrider_db is None:
        ccrider_db = Path.home() / ".config" / "ccrider" / "sessions.db"
    if ccrider_db.is_file():
        targets["ccrider"].append(ccrider_db)

    return targets
```

**Step 4: Run tests to verify they pass**

Run: `python3 tests/test_claude_scrub.py TestFileDiscovery -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: file discovery for all Claude Code data targets

Add discover_targets() that finds session .jsonl files, index
files, history.jsonl, paste-cache, file-history, and ccrider DB.
Handles missing directories gracefully."
```

---

### Task 4: Scan command

**Files:**
- Modify: `claude-scrub`
- Modify: `tests/test_claude_scrub.py`

**Step 1: Write the failing tests**

Add to `tests/test_claude_scrub.py`:

```python
class TestScanCommand(unittest.TestCase):
    """Test the scan command logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.claude_dir = Path(self.tmpdir) / ".claude"
        proj = self.claude_dir / "projects" / "-Users-test-Code-myapp"
        proj.mkdir(parents=True)

        # Session with secrets
        (proj / "abc123.jsonl").write_text(
            '{"message":"my key is AKIAIOSFODNN7EXAMPLE"}\n'
            '{"message":"also sk_live_abcdefghij1234567890"}\n'
        )
        # Clean session
        (proj / "clean.jsonl").write_text('{"message":"nothing secret here"}\n')

        # History with secret
        (self.claude_dir / "history.jsonl").write_text(
            '{"prompt":"set token=ghp_ABCDEFghijklmnopqrst1234567890ab"}\n'
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_scan_returns_results_per_category(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir)
        results = cs.scan_targets(targets, patterns)
        self.assertIn("sessions", results)
        self.assertIn("history", results)

    def test_scan_counts_secrets_in_sessions(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir)
        results = cs.scan_targets(targets, patterns)
        total = sum(len(m) for m in results["sessions"].values())
        self.assertGreaterEqual(total, 2)  # AWS key + Stripe key

    def test_scan_counts_secrets_in_history(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir)
        results = cs.scan_targets(targets, patterns)
        total = sum(len(m) for m in results["history"].values())
        self.assertGreaterEqual(total, 1)  # GitHub token

    def test_scan_clean_files_have_no_matches(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir)
        results = cs.scan_targets(targets, patterns)
        clean_file = self.claude_dir / "projects" / "-Users-test-Code-myapp" / "clean.jsonl"
        matches = results["sessions"].get(clean_file, [])
        self.assertEqual(len(matches), 0)

    def test_format_scan_summary(self):
        """Summary output should include totals."""
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir)
        results = cs.scan_targets(targets, patterns)
        output = cs.format_scan_report(results, verbose=False)
        self.assertIn("secrets found", output)
        self.assertIn("Total:", output)

    def test_format_scan_verbose(self):
        """Verbose output should include file paths and line numbers."""
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir)
        results = cs.scan_targets(targets, patterns)
        output = cs.format_scan_report(results, verbose=True)
        self.assertIn("abc123.jsonl", output)
        self.assertIn("Line", output)
```

**Step 2: Run tests to verify they fail**

Run: `python3 tests/test_claude_scrub.py TestScanCommand -v`
Expected: FAIL — `scan_targets`, `format_scan_report` don't exist

**Step 3: Implement scan logic**

Add to `claude-scrub`:

```python
# Display names for target categories
CATEGORY_LABELS = {
    "sessions": "Sessions",
    "indexes": "Index files",
    "history": "History",
    "paste_cache": "Paste cache",
    "file_history": "File history",
    "ccrider": "ccrider DB",
}


def scan_targets(targets, patterns):
    """Scan all target files for secrets.

    Returns dict of category -> {filepath: [(name, match_text, line_num), ...]}.
    Files with no matches are omitted from the inner dict.
    """
    results = {}
    for category, files in targets.items():
        file_results = {}
        for filepath in files:
            try:
                text = filepath.read_text(errors="replace")
            except OSError:
                continue
            matches = find_secrets(text, patterns)
            if matches:
                file_results[filepath] = matches
        results[category] = file_results
    return results


def format_scan_report(results, verbose=False):
    """Format scan results as a human-readable report."""
    lines = ["Scanning Claude Code data...", ""]

    total_files = 0
    total_secrets = 0

    for category in ("sessions", "indexes", "history", "paste_cache", "file_history", "ccrider"):
        if category not in results:
            continue
        file_results = results[category]
        label = CATEGORY_LABELS.get(category, category)

        # Count all files scanned (including clean ones — we need the target counts)
        # file_results only has files WITH matches, so we note that in the label
        secret_count = sum(len(m) for m in file_results.values())
        file_count = len(file_results)
        total_files += file_count
        total_secrets += secret_count

        noun = "secret" if secret_count == 1 else "secrets"
        file_noun = "file" if file_count == 1 else "files"
        lines.append(f"{label + ':':<16}{file_count} {file_noun} with {secret_count} {noun}")

        if verbose and file_results:
            for filepath, matches in sorted(file_results.items()):
                short = shorten_project(str(filepath))
                lines.append(f"  {short}: {len(matches)} secrets")
                for name, match_text, line_num in matches:
                    # Show first 20 chars of match, redacted
                    preview = match_text[:20] + "..." if len(match_text) > 20 else match_text
                    lines.append(f"    Line {line_num}: {name} ({preview})")

    lines.append("")
    noun = "secret" if total_secrets == 1 else "secrets"
    file_noun = "file" if total_files == 1 else "files"
    lines.append(f"Total: {total_secrets} {noun} found across {total_files} {file_noun}")

    return "\n".join(lines)
```

Update `cmd_scan` to use the real implementation:

```python
def cmd_scan(args):
    """Scan Claude Code data for secrets (read-only)."""
    patterns = get_builtin_patterns()
    targets = discover_targets(CLAUDE_DIR)
    results = scan_targets(targets, patterns)
    print(format_scan_report(results, verbose=args.verbose))
```

**Step 4: Run tests to verify they pass**

Run: `python3 tests/test_claude_scrub.py TestScanCommand -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: scan command for read-only secret auditing

Add scan_targets() and format_scan_report() with summary and
verbose output modes. Scan walks all discovered files, runs
named pattern matching, and reports per-category totals."
```

---

### Task 5: Scrub command

**Files:**
- Modify: `claude-scrub`
- Modify: `tests/test_claude_scrub.py`

**Step 1: Write the failing tests**

Add to `tests/test_claude_scrub.py`:

```python
class TestScrubCommand(unittest.TestCase):
    """Test the scrub command logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.claude_dir = Path(self.tmpdir) / ".claude"
        proj = self.claude_dir / "projects" / "-Users-test-Code-myapp"
        proj.mkdir(parents=True)

        self.secret_file = proj / "abc123.jsonl"
        self.secret_file.write_text(
            '{"message":"key is AKIAIOSFODNN7EXAMPLE here"}\n'
            '{"message":"clean line"}\n'
        )

        self.history = self.claude_dir / "history.jsonl"
        self.history.write_text('{"prompt":"token=ghp_ABCDEFghijklmnopqrst1234567890ab"}\n')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_scrub_replaces_secrets_in_files(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir)
        stats = cs.scrub_targets(targets, patterns)
        content = self.secret_file.read_text()
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", content)
        self.assertIn("[REDACTED:", content)
        # Clean line should be untouched
        self.assertIn("clean line", content)

    def test_scrub_replaces_secrets_in_history(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir)
        cs.scrub_targets(targets, patterns)
        content = self.history.read_text()
        self.assertNotIn("ghp_ABCDEF", content)
        self.assertIn("[REDACTED:", content)

    def test_scrub_returns_stats(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir)
        stats = cs.scrub_targets(targets, patterns)
        self.assertGreater(stats["total_secrets"], 0)
        self.assertGreater(stats["total_files"], 0)

    def test_scrub_respects_include_filter(self):
        """Paste cache should only be scrubbed when included."""
        paste_dir = self.claude_dir / "paste-cache"
        paste_dir.mkdir()
        paste_file = paste_dir / "paste1.txt"
        paste_file.write_text("secret: AKIAIOSFODNN7EXAMPLE")

        patterns = cs.get_builtin_patterns()

        # Default scrub should NOT touch paste cache
        targets = cs.discover_targets(self.claude_dir)
        default_targets = cs.filter_scrub_targets(targets, include="")
        self.assertEqual(len(default_targets["paste_cache"]), 0)

        # With include, should touch paste cache
        included_targets = cs.filter_scrub_targets(targets, include="paste-cache")
        self.assertEqual(len(included_targets["paste_cache"]), 1)

    def test_scrub_idempotent(self):
        """Running scrub twice should not change already-scrubbed content."""
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir)
        cs.scrub_targets(targets, patterns)
        content_after_first = self.secret_file.read_text()

        targets2 = cs.discover_targets(self.claude_dir)
        cs.scrub_targets(targets2, patterns)
        content_after_second = self.secret_file.read_text()

        self.assertEqual(content_after_first, content_after_second)
```

**Step 2: Run tests to verify they fail**

Run: `python3 tests/test_claude_scrub.py TestScrubCommand -v`
Expected: FAIL — `scrub_targets`, `filter_scrub_targets` don't exist

**Step 3: Implement scrub logic**

Add to `claude-scrub`:

```python
def filter_scrub_targets(targets, include=""):
    """Filter targets for scrubbing. Sessions, indexes, and history are always included.
    Paste cache, file history, and ccrider require explicit opt-in via --include.
    """
    included = set(s.strip() for s in include.split(",") if s.strip())

    filtered = {
        "sessions": targets.get("sessions", []),
        "indexes": targets.get("indexes", []),
        "history": targets.get("history", []),
        "paste_cache": targets["paste_cache"] if "paste-cache" in included else [],
        "file_history": targets["file_history"] if "file-history" in included else [],
        "ccrider": targets["ccrider"] if "ccrider" in included else [],
    }
    return filtered


def scrub_targets(targets, patterns):
    """Scrub secrets from all target files in-place.

    Returns stats dict with total_secrets, total_files, per_category counts.
    """
    stats = {"total_secrets": 0, "total_files": 0, "categories": {}}

    for category, files in targets.items():
        cat_secrets = 0
        cat_files = 0
        for filepath in files:
            try:
                original = filepath.read_text(errors="replace")
            except OSError:
                continue
            scrubbed = redact_secrets(original, patterns)
            if scrubbed != original:
                filepath.write_text(scrubbed)
                cat_files += 1
                # Count how many replacements were made
                cat_secrets += len(find_secrets(original, patterns))

        stats["categories"][category] = {"secrets": cat_secrets, "files": cat_files}
        stats["total_secrets"] += cat_secrets
        stats["total_files"] += cat_files

    return stats
```

Update `cmd_scrub`:

```python
def cmd_scrub(args):
    """Scrub secrets from Claude Code data files."""
    patterns = get_builtin_patterns()
    all_targets = discover_targets(CLAUDE_DIR)

    # First, scan everything to show the user what we found
    scan_results = scan_targets(all_targets, patterns)
    print(format_scan_report(scan_results, verbose=args.verbose))

    total = sum(sum(len(m) for m in cat.values()) for cat in scan_results.values())
    if total == 0:
        print("\nNo secrets found. Nothing to scrub.")
        return

    # Filter targets for scrubbing (opt-in categories)
    scrub_targets_filtered = filter_scrub_targets(all_targets, include=args.include)

    # Confirm
    if not args.yes:
        answer = input(f"\nScrub {total} secrets? This cannot be undone. [y/N] ")
        if answer.lower() != "y":
            print("Aborted.")
            return

    stats = scrub_targets(scrub_targets_filtered, patterns)
    print(f"\nScrubbed {stats['total_secrets']} secrets across {stats['total_files']} files.")
```

**Step 4: Run tests to verify they pass**

Run: `python3 tests/test_claude_scrub.py TestScrubCommand -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: scrub command with opt-in targets and confirmation

Add scrub_targets() for in-place secret redaction and
filter_scrub_targets() for opt-in control of paste-cache,
file-history, and ccrider. Scrub runs a scan first, prompts
for confirmation, then replaces secrets with [REDACTED:<name>]."
```

---

### Task 6: Custom patterns config

**Files:**
- Modify: `claude-scrub`
- Modify: `tests/test_claude_scrub.py`

**Step 1: Write the failing tests**

Add to `tests/test_claude_scrub.py`:

```python
class TestCustomPatterns(unittest.TestCase):
    """Test loading custom patterns from TOML config."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_dir = Path(self.tmpdir) / ".config" / "claude-scrub"
        self.config_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_load_custom_patterns_from_toml(self):
        config = self.config_dir / "config.toml"
        config.write_text(
            '[[patterns]]\n'
            'name = "Internal Key"\n'
            'regex = "myco_[a-zA-Z0-9]{32}"\n'
            '\n'
            '[[patterns]]\n'
            'name = "DB URL"\n'
            'regex = "postgres://[^\\\\s]+"\n'
        )
        patterns = cs.load_custom_patterns(config)
        self.assertEqual(len(patterns), 2)
        self.assertEqual(patterns[0]["name"], "Internal Key")
        self.assertIsNotNone(patterns[0]["regex"].pattern)

    def test_load_custom_patterns_missing_file(self):
        """Missing config file should return empty list, not error."""
        patterns = cs.load_custom_patterns(self.config_dir / "nonexistent.toml")
        self.assertEqual(len(patterns), 0)

    def test_custom_pattern_matches(self):
        config = self.config_dir / "config.toml"
        config.write_text(
            '[[patterns]]\n'
            'name = "Internal Key"\n'
            'regex = "myco_[a-zA-Z0-9]{32}"\n'
        )
        custom = cs.load_custom_patterns(config)
        text = "key=myco_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef"
        matches = cs.find_secrets(text, custom)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][0], "Internal Key")

    def test_invalid_regex_skipped(self):
        """Invalid regex in config should be skipped with warning, not crash."""
        config = self.config_dir / "config.toml"
        config.write_text(
            '[[patterns]]\n'
            'name = "Bad Regex"\n'
            'regex = "[invalid(("\n'
            '\n'
            '[[patterns]]\n'
            'name = "Good One"\n'
            'regex = "good_[a-z]+"\n'
        )
        patterns = cs.load_custom_patterns(config)
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["name"], "Good One")
```

**Step 2: Run tests to verify they fail**

Run: `python3 tests/test_claude_scrub.py TestCustomPatterns -v`
Expected: FAIL — `load_custom_patterns` doesn't exist

**Step 3: Implement TOML config loading**

Add to `claude-scrub`:

```python
def parse_simple_toml(text):
    """Minimal TOML parser for [[patterns]] arrays of tables.

    Only supports the subset we need: [[patterns]] with string keys.
    Uses stdlib tomllib on Python 3.11+, falls back to this parser.
    """
    try:
        import tomllib
        return tomllib.loads(text)
    except ImportError:
        pass

    # Minimal fallback parser for [[patterns]] tables
    result = {}
    current_array_key = None
    current_item = None

    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Array of tables header: [[patterns]]
        if line.startswith("[[") and line.endswith("]]"):
            if current_item is not None and current_array_key is not None:
                result.setdefault(current_array_key, []).append(current_item)
            current_array_key = line[2:-2].strip()
            current_item = {}
            continue

        # Key = "value"
        if "=" in line and current_item is not None:
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            # Strip quotes
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            # Handle basic escape sequences
            val = val.replace("\\\\", "\x00").replace("\\n", "\n").replace("\\t", "\t").replace("\x00", "\\")
            current_item[key] = val

    # Don't forget the last item
    if current_item is not None and current_array_key is not None:
        result.setdefault(current_array_key, []).append(current_item)

    return result


def load_custom_patterns(config_path):
    """Load custom patterns from a TOML config file.

    Returns list of {"name": str, "regex": compiled_regex}.
    Invalid regexes are skipped with a warning.
    """
    if not config_path.is_file():
        return []

    try:
        text = config_path.read_text()
    except OSError:
        return []

    data = parse_simple_toml(text)
    patterns = []

    for entry in data.get("patterns", []):
        name = entry.get("name", "")
        regex_str = entry.get("regex", "")
        if not name or not regex_str:
            continue
        try:
            compiled = re.compile(regex_str)
            patterns.append({"name": name, "regex": compiled})
        except re.error:
            print(f"Warning: invalid regex for pattern '{name}', skipping", file=sys.stderr)

    return patterns
```

Wire custom patterns into `cmd_scan` and `cmd_scrub`:

```python
CONFIG_DIR = Path.home() / ".config" / "claude-scrub"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def load_all_patterns(use_patterns_db=False):
    """Load built-in + custom patterns (and optionally patterns-db)."""
    patterns = get_builtin_patterns()
    custom = load_custom_patterns(CONFIG_FILE)
    if custom:
        patterns.extend(custom)
    return patterns
```

Update `cmd_scan` and `cmd_scrub` to call `load_all_patterns(args.patterns_db)` instead of `get_builtin_patterns()`.

**Step 4: Run tests to verify they pass**

Run: `python3 tests/test_claude_scrub.py TestCustomPatterns -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: custom pattern support via TOML config

Add load_custom_patterns() with stdlib tomllib (3.11+) and
minimal fallback parser. Custom patterns from
~/.config/claude-scrub/config.toml are merged with built-ins.
Invalid regexes are skipped with a warning."
```

---

### Task 7: patterns-db integration

**Files:**
- Modify: `claude-scrub`
- Modify: `tests/test_claude_scrub.py`

**Step 1: Write the failing tests**

Add to `tests/test_claude_scrub.py`:

```python
class TestPatternsDB(unittest.TestCase):
    """Test loading patterns from secrets-patterns-db."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache_dir = Path(self.tmpdir) / "patterns-db"
        self.cache_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_parse_gitleaks_format(self):
        """Should parse gitleaks TOML format into patterns."""
        gitleaks_toml = (
            '[[rules]]\n'
            'id = "aws-access-key"\n'
            'description = "AWS Access Key"\n'
            'regex = "(?:AKIA|ASIA)[0-9A-Z]{16}"\n'
            '\n'
            '[[rules]]\n'
            'id = "github-pat"\n'
            'description = "GitHub PAT"\n'
            'regex = "ghp_[A-Za-z0-9_]{36}"\n'
        )
        (self.cache_dir / "gitleaks.toml").write_text(gitleaks_toml)
        patterns = cs.load_patterns_db(self.cache_dir / "gitleaks.toml")
        self.assertEqual(len(patterns), 2)
        self.assertEqual(patterns[0]["name"], "AWS Access Key")
        self.assertEqual(patterns[1]["name"], "GitHub PAT")

    def test_parse_gitleaks_invalid_regex(self):
        """Invalid regexes in patterns-db should be skipped."""
        gitleaks_toml = (
            '[[rules]]\n'
            'id = "bad"\n'
            'description = "Bad Pattern"\n'
            'regex = "[invalid((regex"\n'
        )
        (self.cache_dir / "gitleaks.toml").write_text(gitleaks_toml)
        patterns = cs.load_patterns_db(self.cache_dir / "gitleaks.toml")
        self.assertEqual(len(patterns), 0)

    def test_load_patterns_db_missing_file(self):
        """Missing file should return empty list."""
        patterns = cs.load_patterns_db(self.cache_dir / "nonexistent.toml")
        self.assertEqual(len(patterns), 0)
```

**Step 2: Run tests to verify they fail**

Run: `python3 tests/test_claude_scrub.py TestPatternsDB -v`
Expected: FAIL — `load_patterns_db` doesn't exist

**Step 3: Implement patterns-db loading**

Add to `claude-scrub`:

```python
PATTERNS_DB_URL = "https://raw.githubusercontent.com/mazen160/secrets-patterns-db/master/db/rules-stable.yml"
PATTERNS_DB_TOML_URL = "https://raw.githubusercontent.com/mazen160/secrets-patterns-db/master/db/gitleaks/gitleaks.toml"
PATTERNS_DB_CACHE = CONFIG_DIR / "patterns-db" / "gitleaks.toml"


def load_patterns_db(toml_path):
    """Load patterns from a gitleaks-format TOML file.

    The gitleaks format uses [[rules]] with id, description, and regex fields.
    Returns list of {"name": str, "regex": compiled_regex}.
    """
    if not toml_path.is_file():
        return []

    try:
        text = toml_path.read_text()
    except OSError:
        return []

    data = parse_simple_toml(text)
    patterns = []

    for rule in data.get("rules", []):
        name = rule.get("description", rule.get("id", "unknown"))
        regex_str = rule.get("regex", "")
        if not regex_str:
            continue
        try:
            compiled = re.compile(regex_str)
            patterns.append({"name": name, "regex": compiled})
        except re.error:
            continue  # Skip invalid regexes silently for bulk import

    return patterns


def download_patterns_db():
    """Download secrets-patterns-db gitleaks TOML to local cache."""
    import urllib.request

    PATTERNS_DB_CACHE.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading patterns-db to {PATTERNS_DB_CACHE}...")
    try:
        urllib.request.urlretrieve(PATTERNS_DB_TOML_URL, PATTERNS_DB_CACHE)
        print(f"Downloaded. Use --patterns-db to include in future scans.")
    except Exception as e:
        print(f"Error downloading patterns-db: {e}", file=sys.stderr)
        return False
    return True
```

Update `load_all_patterns`:

```python
def load_all_patterns(use_patterns_db=False):
    """Load built-in + custom patterns (and optionally patterns-db)."""
    patterns = get_builtin_patterns()
    custom = load_custom_patterns(CONFIG_FILE)
    if custom:
        patterns.extend(custom)
    if use_patterns_db:
        if not PATTERNS_DB_CACHE.is_file():
            download_patterns_db()
        db_patterns = load_patterns_db(PATTERNS_DB_CACHE)
        if db_patterns:
            patterns.extend(db_patterns)
            print(f"Loaded {len(db_patterns)} patterns from patterns-db", file=sys.stderr)
    return patterns
```

**Step 4: Run tests to verify they pass**

Run: `python3 tests/test_claude_scrub.py TestPatternsDB -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: secrets-patterns-db integration via --patterns-db

Add load_patterns_db() for gitleaks TOML format and
download_patterns_db() to fetch and cache the community
patterns. Integrates into load_all_patterns() when
--patterns-db flag is used."
```

---

### Task 8: Update scan report with file counts from targets

**Files:**
- Modify: `claude-scrub`
- Modify: `tests/test_claude_scrub.py`

The current `format_scan_report` only knows about files WITH matches. We need to also show total files scanned (including clean ones).

**Step 1: Write the failing test**

Add to `TestScanCommand`:

```python
    def test_format_scan_shows_total_files_scanned(self):
        """Report should show total files scanned, not just files with secrets."""
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir)
        results = cs.scan_targets(targets, patterns)
        output = cs.format_scan_report(results, verbose=False, targets=targets)
        # We have 2 session files + 1 history = 3 total, but only some have secrets
        self.assertIn("scanned", output)
```

**Step 2: Run test to verify it fails**

Run: `python3 tests/test_claude_scrub.py TestScanCommand.test_format_scan_shows_total_files_scanned -v`
Expected: FAIL — `format_scan_report` doesn't accept `targets` kwarg

**Step 3: Update format_scan_report signature**

Update `format_scan_report` to accept optional `targets` dict for file counts:

```python
def format_scan_report(results, verbose=False, targets=None):
    """Format scan results as a human-readable report."""
    lines = ["Scanning Claude Code data...", ""]

    total_files_scanned = 0
    total_secrets = 0

    for category in ("sessions", "indexes", "history", "paste_cache", "file_history", "ccrider"):
        if category not in results:
            continue
        file_results = results[category]
        label = CATEGORY_LABELS.get(category, category)

        scanned_count = len(targets[category]) if targets and category in targets else len(file_results)
        secret_count = sum(len(m) for m in file_results.values())
        files_with_secrets = len(file_results)
        total_files_scanned += scanned_count
        total_secrets += secret_count

        file_noun = "file" if scanned_count == 1 else "files"
        noun = "secret" if secret_count == 1 else "secrets"
        lines.append(f"{label + ':':<16}{scanned_count} {file_noun} scanned, {secret_count} {noun} found")

        if verbose and file_results:
            for filepath, matches in sorted(file_results.items()):
                short = shorten_project(str(filepath))
                lines.append(f"  {short}: {len(matches)} secrets")
                for name, match_text, line_num in matches:
                    preview = match_text[:20] + "..." if len(match_text) > 20 else match_text
                    lines.append(f"    Line {line_num}: {name} ({preview})")

    lines.append("")
    noun = "secret" if total_secrets == 1 else "secrets"
    file_noun = "file" if total_files_scanned == 1 else "files"
    lines.append(f"Total: {total_secrets} {noun} found across {total_files_scanned} {file_noun}")

    return "\n".join(lines)
```

Update callers (`cmd_scan`, `cmd_scrub`) to pass `targets=targets`.

**Step 4: Run tests to verify they pass**

Run: `python3 tests/test_claude_scrub.py TestScanCommand -v`
Expected: All 7 tests PASS (update existing tests that call `format_scan_report` to also pass `targets` if needed, or make the parameter optional)

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "fix: scan report shows total files scanned not just matches

Pass targets dict to format_scan_report so it can show
'142 files scanned, 7 secrets found' instead of only
counting files that had matches."
```

---

### Task 9: Update README and clean up

**Files:**
- Modify: `README.md`
- Modify: `claude-scrub` (ABOUTME lines)

**Step 1: Update ABOUTME lines**

Change the top of `claude-scrub`:

```python
#!/usr/bin/env python3
# ABOUTME: Scan and scrub secrets from Claude Code local session data.
# ABOUTME: Also lists sessions with resume commands. Zero dependencies.
```

**Step 2: Update README.md**

Rewrite `README.md` to document `claude-scrub` with its three commands, install instructions, and examples. Keep the secret scrubbing section. Add the `--patterns-db` and config file documentation.

Key sections:
- What it does (scan, scrub, sessions)
- Install (same curl pattern, new filename)
- Usage examples for each command
- Custom patterns config
- patterns-db integration
- How it works (target files)
- License

**Step 3: Run all tests one final time**

Run: `python3 tests/test_claude_scrub.py -v`
Expected: ALL tests PASS

**Step 4: Commit**

```bash
git add claude-scrub README.md
git commit -m "docs: update README and ABOUTME for claude-scrub

Rewrite README to document scan, scrub, and sessions commands.
Add custom patterns and patterns-db documentation."
```

---

### Task 10: End-to-end test

**Files:**
- Modify: `tests/test_claude_scrub.py`

**Step 1: Write the e2e test**

Add to `tests/test_claude_scrub.py`:

```python
class TestEndToEnd(unittest.TestCase):
    """End-to-end test: scan finds secrets, scrub removes them, re-scan finds none."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.claude_dir = Path(self.tmpdir) / ".claude"
        proj = self.claude_dir / "projects" / "-Users-test-Code-app"
        proj.mkdir(parents=True)

        (proj / "session1.jsonl").write_text(
            '{"message":"AWS key: AKIAIOSFODNN7EXAMPLE"}\n'
            '{"message":"Stripe: sk_live_abcdefghij1234567890"}\n'
        )
        (proj / "session2.jsonl").write_text(
            '{"message":"no secrets here"}\n'
        )

        (self.claude_dir / "history.jsonl").write_text(
            '{"prompt":"ghp_ABCDEFghijklmnopqrst1234567890ab"}\n'
        )

        paste = self.claude_dir / "paste-cache"
        paste.mkdir()
        (paste / "p1.txt").write_text("token: sk-ant-api03-AAAAABBBBCCCCDDDDEEEE1234567890abcdef")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_full_scan_scrub_rescan_cycle(self):
        patterns = cs.get_builtin_patterns()

        # 1. Scan — should find secrets
        targets = cs.discover_targets(self.claude_dir)
        results = cs.scan_targets(targets, patterns)
        initial_count = sum(
            len(m) for cat in results.values() for m in cat.values()
        )
        self.assertGreater(initial_count, 0)

        # 2. Scrub sessions + history (default targets)
        scrub_targets = cs.filter_scrub_targets(targets, include="")
        stats = cs.scrub_targets(scrub_targets, patterns)
        self.assertGreater(stats["total_secrets"], 0)

        # 3. Re-scan sessions + history — should find no secrets
        targets2 = cs.discover_targets(self.claude_dir)
        results2 = cs.scan_targets(targets2, patterns)
        session_secrets = sum(len(m) for m in results2["sessions"].values())
        history_secrets = sum(len(m) for m in results2["history"].values())
        self.assertEqual(session_secrets, 0)
        self.assertEqual(history_secrets, 0)

        # 4. Paste cache should still have secrets (not included in default scrub)
        paste_secrets = sum(len(m) for m in results2["paste_cache"].values())
        self.assertGreater(paste_secrets, 0)

        # 5. Scrub with paste-cache included
        targets3 = cs.discover_targets(self.claude_dir)
        scrub_targets3 = cs.filter_scrub_targets(targets3, include="paste-cache")
        cs.scrub_targets(scrub_targets3, patterns)

        # 6. Final re-scan — everything clean
        targets4 = cs.discover_targets(self.claude_dir)
        results4 = cs.scan_targets(targets4, patterns)
        final_count = sum(
            len(m) for cat in results4.values() for m in cat.values()
        )
        self.assertEqual(final_count, 0)
```

**Step 2: Run the e2e test**

Run: `python3 tests/test_claude_scrub.py TestEndToEnd -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `python3 tests/test_claude_scrub.py -v`
Expected: ALL tests PASS

**Step 4: Commit**

```bash
git add tests/test_claude_scrub.py
git commit -m "test: add end-to-end scan-scrub-rescan cycle test

Verify that scan finds secrets, scrub removes them from default
targets, paste-cache is only scrubbed when included, and a
final re-scan confirms everything is clean."
```

---

## Post-Implementation

After all tasks are complete:
1. Run `python3 tests/test_claude_scrub.py -v` — all tests must pass
2. Run `python3 claude-scrub scan` against real `~/.claude` to verify
3. Update Skyler's alias in `~/.zshrc` from `claude-sessions` to `claude-scrub sessions`
4. Rename GitHub repo from `claude-sessions-cli` to `claude-scrub` (manual step)
5. Push to GitHub
