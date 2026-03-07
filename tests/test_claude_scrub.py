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

    def test_find_secrets_deduplicates_generic_when_specific_matches(self):
        """Generic Secret Assignment should be suppressed when a specific pattern matches same text."""
        # "token = glpat-ABCDEFGHIJ1234567890" matches both GitLab Token and Generic Secret Assignment
        text = "token = glpat-ABCDEFGHIJ1234567890"
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        names = [m[0] for m in matches]
        self.assertIn("GitLab Token", names)
        self.assertNotIn("Generic Secret Assignment", names)
        self.assertEqual(len(matches), 1)

    def test_find_secrets_keeps_generic_when_no_specific_matches(self):
        """Generic Secret Assignment should remain when no specific pattern matches."""
        text = "secret = mysuperlong_internal_key_value_here"
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        names = [m[0] for m in matches]
        self.assertIn("Generic Secret Assignment", names)

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

    def test_format_scan_shows_total_files_scanned(self):
        """Report should show total files scanned, not just files with secrets."""
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results = cs.scan_targets(targets, patterns)
        output = cs.format_scan_report(results, verbose=False, targets=targets)
        self.assertIn("scanned", output)

    def test_progress_shows_global_counter(self):
        """Progress output should include [N/M] global file counter."""
        import io
        from contextlib import redirect_stdout
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        total_files = sum(len(v) for v in targets.values())
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.scan_targets(targets, patterns, show_progress=True)
        output = buf.getvalue()
        # Should contain the global counter prefix like [3/3]
        self.assertRegex(output, r"\[\d+/\d+\]")
        # Final global count should match total files
        self.assertIn(f"[{total_files}/{total_files}]", output)

    def test_progress_shows_secret_tally(self):
        """Progress output should show running secret count when secrets exist."""
        import io
        from contextlib import redirect_stdout
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.scan_targets(targets, patterns, show_progress=True)
        output = buf.getvalue()
        # Sessions category has secrets, so tally should appear
        self.assertRegex(output, r"\d+ secrets")

    def test_progress_no_eta_when_fast(self):
        """ETA should not appear when scan completes in under 1 second."""
        import io
        from contextlib import redirect_stdout
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.scan_targets(targets, patterns, show_progress=True)
        output = buf.getvalue()
        self.assertNotIn("ETA", output)


class TestPrintScanTotalsElapsed(unittest.TestCase):

    def test_totals_with_elapsed_time(self):
        """print_scan_totals should include elapsed time when provided."""
        import io
        from contextlib import redirect_stdout
        results = {"sessions": {}, "indexes": {}, "history": {},
                   "paste_cache": {}, "file_history": {}, "ccrider": {}}
        summary = {"sessions": 5, "indexes": 2, "history": 1,
                   "paste_cache": 0, "file_history": 0, "ccrider": 0}
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_scan_totals(results, summary, elapsed=2.345)
        output = buf.getvalue()
        self.assertIn("(2.3s)", output)

    def test_totals_shows_rotation_warning_when_secrets_found(self):
        """print_scan_totals should warn about credential rotation when secrets exist."""
        import io
        from contextlib import redirect_stdout
        fake_path = Path("/tmp/fake.jsonl")
        results = {"sessions": {fake_path: [("AWS Key", "AKIA...", 1)]}, "indexes": {},
                   "history": {}, "paste_cache": {}, "file_history": {}, "ccrider": {}}
        summary = {"sessions": 1, "indexes": 0, "history": 0,
                   "paste_cache": 0, "file_history": 0, "ccrider": 0}
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_scan_totals(results, summary)
        output = buf.getvalue()
        self.assertIn("rotated", output)

    def test_totals_no_rotation_warning_when_clean(self):
        """print_scan_totals should not warn about rotation when no secrets found."""
        import io
        from contextlib import redirect_stdout
        results = {"sessions": {}, "indexes": {}, "history": {},
                   "paste_cache": {}, "file_history": {}, "ccrider": {}}
        summary = {"sessions": 5, "indexes": 0, "history": 0,
                   "paste_cache": 0, "file_history": 0, "ccrider": 0}
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_scan_totals(results, summary)
        output = buf.getvalue()
        self.assertNotIn("rotated", output)

    def test_totals_without_elapsed_time(self):
        """print_scan_totals should not show timing when elapsed is None."""
        import io
        from contextlib import redirect_stdout
        results = {"sessions": {}, "indexes": {}, "history": {},
                   "paste_cache": {}, "file_history": {}, "ccrider": {}}
        summary = {"sessions": 5, "indexes": 2, "history": 1,
                   "paste_cache": 0, "file_history": 0, "ccrider": 0}
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_scan_totals(results, summary)
        output = buf.getvalue()
        self.assertNotRegex(output, r"\(\d+\.?\d*s\)")


class TestIsClaudeCodeRunning(unittest.TestCase):

    def test_returns_bool(self):
        """is_claude_code_running should return a boolean."""
        result = cs.is_claude_code_running()
        self.assertIsInstance(result, bool)


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


class TestPatternsDB(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache_dir = Path(self.tmpdir) / "patterns-db"
        self.cache_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_parse_gitleaks_format(self):
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
        patterns = cs.load_patterns_db(self.cache_dir / "nonexistent.toml")
        self.assertEqual(len(patterns), 0)


class TestEntropy(unittest.TestCase):

    def test_single_char_string(self):
        """All-same characters have zero entropy."""
        self.assertAlmostEqual(cs.entropy("aaaaaa"), 0.0, places=2)

    def test_two_equal_chars(self):
        """Two equally frequent characters have entropy of 1.0 bit."""
        self.assertAlmostEqual(cs.entropy("aabb"), 1.0, places=2)

    def test_empty_string(self):
        self.assertEqual(cs.entropy(""), 0.0)

    def test_high_entropy_random_key(self):
        """Random-looking API key should have high entropy."""
        self.assertGreater(cs.entropy("sK3j8fAx7mNp2qRw"), 3.5)

    def test_low_entropy_english_word(self):
        """Common English word should have low entropy."""
        self.assertLess(cs.entropy("development"), 3.5)

    def test_config_value_low_entropy(self):
        """Config-style values should have low entropy."""
        self.assertLess(cs.entropy("development_mode"), 3.5)

    def test_placeholder_low_entropy(self):
        self.assertLess(cs.entropy("placeholder123"), 3.6)


class TestEndToEnd(unittest.TestCase):
    """End-to-end test: scan finds secrets, scrub removes them, re-scan finds none."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.claude_dir = Path(self.tmpdir) / ".claude"
        self.no_ccrider = Path(self.tmpdir) / "no-ccrider.db"
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
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results = cs.scan_targets(targets, patterns)
        initial_count = sum(
            len(m) for cat in results.values() for m in cat.values()
        )
        self.assertGreater(initial_count, 0)

        # 2. Scrub sessions + history (default targets)
        scrub_tgts = cs.filter_scrub_targets(targets, include="")
        stats = cs.scrub_targets(scrub_tgts, patterns)
        self.assertGreater(stats["total_secrets"], 0)

        # 3. Re-scan sessions + history — should find no secrets
        targets2 = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results2 = cs.scan_targets(targets2, patterns)
        session_secrets = sum(len(m) for m in results2["sessions"].values())
        history_secrets = sum(len(m) for m in results2["history"].values())
        self.assertEqual(session_secrets, 0)
        self.assertEqual(history_secrets, 0)

        # 4. Paste cache should still have secrets (not included in default scrub)
        paste_secrets = sum(len(m) for m in results2["paste_cache"].values())
        self.assertGreater(paste_secrets, 0)

        # 5. Scrub with paste-cache included
        targets3 = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        scrub_tgts3 = cs.filter_scrub_targets(targets3, include="paste-cache")
        cs.scrub_targets(scrub_tgts3, patterns)

        # 6. Final re-scan — everything clean
        targets4 = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results4 = cs.scan_targets(targets4, patterns)
        final_count = sum(
            len(m) for cat in results4.values() for m in cat.values()
        )
        self.assertEqual(final_count, 0)
