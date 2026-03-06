# ABOUTME: Tests for claude-scrub CLI argument parsing.
# ABOUTME: Validates subcommand routing and flag handling via parse_args.

import importlib.machinery
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parent.parent / "claude-scrub"
loader = importlib.machinery.SourceFileLoader("claude_scrub", str(SCRIPT_PATH))
spec = importlib.util.spec_from_loader("claude_scrub", loader, origin=str(SCRIPT_PATH))
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)


def test_scan_subcommand_parses():
    args = cs.parse_args(["scan"])
    assert args.command == "scan"


def test_scrub_subcommand_parses():
    args = cs.parse_args(["scrub"])
    assert args.command == "scrub"


def test_sessions_subcommand_parses():
    args = cs.parse_args(["sessions"])
    assert args.command == "sessions"


def test_scan_verbose_flag():
    args = cs.parse_args(["scan", "--verbose"])
    assert args.verbose is True


def test_scan_patterns_db_flag():
    args = cs.parse_args(["scan", "--patterns-db"])
    assert args.patterns_db is True


def test_scrub_yes_flag():
    args = cs.parse_args(["scrub", "--yes"])
    assert args.yes is True


def test_scrub_include_flag():
    args = cs.parse_args(["scrub", "--include", "paste-cache,file-history"])
    assert args.include == "paste-cache,file-history"


def test_sessions_latest_flag():
    args = cs.parse_args(["sessions", "--latest"])
    assert args.latest is True


def test_sessions_days_flag():
    args = cs.parse_args(["sessions", "--days", "7"])
    assert args.days == 7


def test_no_subcommand_shows_help():
    with pytest.raises(SystemExit):
        cs.parse_args([])


class TestPatternEngine(unittest.TestCase):

    def test_builtin_patterns_are_named(self):
        patterns = cs.get_builtin_patterns()
        self.assertGreater(len(patterns), 30)
        for p in patterns:
            self.assertIn("name", p)
            self.assertIn("regex", p)
            self.assertIsNotNone(p["regex"].pattern)

    def test_find_secrets_returns_matches_with_names(self):
        text = "my key is sk-ant-api03-AAAAABBBBCCCCDDDDEEEE1234567890abcdef"
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        self.assertGreater(len(matches), 0)
        name, match_text, line_num = matches[0]
        self.assertIsInstance(name, str)
        self.assertIn("sk-ant-api03", match_text)
        self.assertEqual(line_num, 1)

    def test_find_secrets_reports_line_numbers(self):
        text = "line one\nAKIAIOSFODNN7EXAMPLE\nline three\nsk_live_abc1234567890"
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        lines = {m[2] for m in matches}
        self.assertIn(2, lines)
        self.assertIn(4, lines)

    def test_find_secrets_empty_text(self):
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets("hello world\nno secrets here", patterns)
        self.assertEqual(len(matches), 0)

    def test_redact_secrets_replaces_with_pattern_name(self):
        text = "key is AKIAIOSFODNN7EXAMPLE"
        patterns = cs.get_builtin_patterns()
        result = cs.redact_secrets(text, patterns)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", result)
        self.assertIn("[REDACTED:", result)

    def test_scrub_secrets_still_works(self):
        text = "token: sk-ant-api03-AAAAABBBBCCCCDDDDEEEE1234567890abcdef"
        result = cs.scrub_secrets(text)
        self.assertNotIn("sk-ant-api03", result)
        self.assertIn("[REDACTED]", result)


class TestFileDiscovery(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.claude_dir = Path(self.tmpdir) / ".claude"

        proj = self.claude_dir / "projects" / "-Users-test-Code-myapp"
        proj.mkdir(parents=True)
        (proj / "abc123.jsonl").write_text('{"type":"user"}\n')
        (proj / "def456.jsonl").write_text('{"type":"user"}\n')
        (proj / "sessions-index.json").write_text('{"entries":[]}')

        (self.claude_dir / "history.jsonl").write_text('{"prompt":"hello"}\n')

        paste = self.claude_dir / "paste-cache"
        paste.mkdir()
        (paste / "paste1.txt").write_text("some pasted content")

        fh = self.claude_dir / "file-history"
        fh.mkdir()
        (fh / "snapshot1.txt").write_text("some code")

    def tearDown(self):
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
        empty = Path(self.tmpdir) / "empty-claude"
        empty.mkdir()
        no_db = Path(self.tmpdir) / "nonexistent" / "sessions.db"
        targets = cs.discover_targets(empty, ccrider_db=no_db)
        for category in targets.values():
            self.assertEqual(len(category), 0)

    def test_discover_finds_ccrider_db(self):
        ccrider_dir = Path(self.tmpdir) / ".config" / "ccrider"
        ccrider_dir.mkdir(parents=True)
        db = ccrider_dir / "sessions.db"
        db.write_text("fake db")
        targets = cs.discover_targets(self.claude_dir, ccrider_db=db)
        self.assertEqual(len(targets["ccrider"]), 1)
