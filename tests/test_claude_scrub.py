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


class TestScanCommand(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.claude_dir = Path(self.tmpdir) / ".claude"
        self.no_ccrider = Path(self.tmpdir) / "nonexistent" / "sessions.db"
        proj = self.claude_dir / "projects" / "-Users-test-Code-myapp"
        proj.mkdir(parents=True)

        (proj / "abc123.jsonl").write_text(
            '{"message":"my key is AKIAIOSFODNN7EXAMPLE"}\n'
            '{"message":"also sk_live_abcdefghij1234567890"}\n'
        )
        (proj / "clean.jsonl").write_text('{"message":"nothing secret here"}\n')
        (self.claude_dir / "history.jsonl").write_text(
            '{"prompt":"set token=ghp_ABCDEFghijklmnopqrst1234567890ab"}\n'
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_scan_returns_results_per_category(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results = cs.scan_targets(targets, patterns)
        self.assertIn("sessions", results)
        self.assertIn("history", results)

    def test_scan_counts_secrets_in_sessions(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results = cs.scan_targets(targets, patterns)
        total = sum(len(m) for m in results["sessions"].values())
        self.assertGreaterEqual(total, 2)

    def test_scan_counts_secrets_in_history(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results = cs.scan_targets(targets, patterns)
        total = sum(len(m) for m in results["history"].values())
        self.assertGreaterEqual(total, 1)

    def test_scan_clean_files_have_no_matches(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results = cs.scan_targets(targets, patterns)
        clean_file = self.claude_dir / "projects" / "-Users-test-Code-myapp" / "clean.jsonl"
        matches = results["sessions"].get(clean_file, [])
        self.assertEqual(len(matches), 0)

    def test_format_scan_summary(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results = cs.scan_targets(targets, patterns)
        output = cs.format_scan_report(results, verbose=False)
        self.assertIn("secrets found", output.lower())
        self.assertIn("Total:", output)

    def test_format_scan_verbose(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results = cs.scan_targets(targets, patterns)
        output = cs.format_scan_report(results, verbose=True)
        self.assertIn("abc123.jsonl", output)
        self.assertIn("Line", output)


class TestScrubCommand(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.claude_dir = Path(self.tmpdir) / ".claude"
        self.no_ccrider = Path(self.tmpdir) / "no-ccrider.db"
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
        shutil.rmtree(self.tmpdir)

    def test_scrub_replaces_secrets_in_files(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        stats = cs.scrub_targets(targets, patterns)
        content = self.secret_file.read_text()
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", content)
        self.assertIn("[REDACTED:", content)
        self.assertIn("clean line", content)

    def test_scrub_replaces_secrets_in_history(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        cs.scrub_targets(targets, patterns)
        content = self.history.read_text()
        self.assertNotIn("ghp_ABCDEF", content)
        self.assertIn("[REDACTED:", content)

    def test_scrub_returns_stats(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        stats = cs.scrub_targets(targets, patterns)
        self.assertGreater(stats["total_secrets"], 0)
        self.assertGreater(stats["total_files"], 0)

    def test_scrub_respects_include_filter(self):
        paste_dir = self.claude_dir / "paste-cache"
        paste_dir.mkdir()
        paste_file = paste_dir / "paste1.txt"
        paste_file.write_text("secret: AKIAIOSFODNN7EXAMPLE")

        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)

        default_targets = cs.filter_scrub_targets(targets, include="")
        self.assertEqual(len(default_targets["paste_cache"]), 0)

        included_targets = cs.filter_scrub_targets(targets, include="paste-cache")
        self.assertEqual(len(included_targets["paste_cache"]), 1)

    def test_scrub_idempotent(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        cs.scrub_targets(targets, patterns)
        content_after_first = self.secret_file.read_text()

        targets2 = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        cs.scrub_targets(targets2, patterns)
        content_after_second = self.secret_file.read_text()

        self.assertEqual(content_after_first, content_after_second)


class TestCustomPatterns(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_dir = Path(self.tmpdir) / ".config" / "claude-scrub"
        self.config_dir.mkdir(parents=True)

    def tearDown(self):
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
