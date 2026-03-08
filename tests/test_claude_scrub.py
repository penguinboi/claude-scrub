# ABOUTME: Tests for claude-scrub CLI argument parsing.
# ABOUTME: Validates subcommand routing and flag handling via parse_args.

import importlib.machinery
import importlib.util
import shutil
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


def test_sessions_negative_days_rejected():
    with pytest.raises(SystemExit):
        cs.parse_args(["sessions", "--days", "-5"])


def test_sessions_zero_days_rejected():
    with pytest.raises(SystemExit):
        cs.parse_args(["sessions", "--days", "0"])


def test_scan_rotation_list_flag():
    args = cs.parse_args(["scan", "--rotation-list"])
    assert args.rotation_list is True


def test_scrub_rotation_list_flag():
    args = cs.parse_args(["scrub", "--rotation-list"])
    assert args.rotation_list is True


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
        name, match_text, line_num, tier = matches[0]
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
        # "api_key = glpat-ABCDEFGHIJ1234567890" matches both GitLab Token and Generic Secret Assignment
        text = "api_key = glpat-ABCDEFGHIJ1234567890"
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        names = [m[0] for m in matches]
        self.assertIn("GitLab Token", names)
        self.assertNotIn("Generic Secret Assignment", names)
        self.assertEqual(len(matches), 1)

    def test_find_secrets_keeps_generic_when_no_specific_matches(self):
        """Generic Secret Assignment should remain when no specific pattern matches."""
        text = "password = mysuperlong_internal_key_value_here"
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

        mem = proj / "memory"
        mem.mkdir()
        (mem / "MEMORY.md").write_text("# Memory\nSome notes")

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

    def test_discover_finds_memory_files(self):
        targets = cs.discover_targets(self.claude_dir)
        self.assertEqual(len(targets["memory"]), 1)
        self.assertTrue(targets["memory"][0].name == "MEMORY.md")

    def test_discover_returns_memory_category(self):
        targets = cs.discover_targets(self.claude_dir)
        self.assertIn("memory", targets)

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
            '{"message":"my key is AKIAIOSFODNN7EXAMPLE"}\n{"message":"also sk_live_abcdefghij1234567890"}\n'
        )
        (proj / "clean.jsonl").write_text('{"message":"nothing secret here"}\n')
        (self.claude_dir / "history.jsonl").write_text('{"prompt":"set token=ghp_ABCDEFghijklmnopqrst1234567890ab"}\n')

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

    def test_scan_finds_secrets_in_memory_files(self):
        mem_dir = self.claude_dir / "projects" / "-Users-test-Code-myapp" / "memory"
        mem_dir.mkdir(exist_ok=True)
        (mem_dir / "MEMORY.md").write_text("api_key = AKIAIOSFODNN7EXAMPLE\n")
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results = cs.scan_targets(targets, patterns)
        self.assertIn("memory", results)
        total = sum(len(m) for m in results["memory"].values())
        self.assertGreaterEqual(total, 1)

    def test_scan_report_shows_memory_category(self):
        mem_dir = self.claude_dir / "projects" / "-Users-test-Code-myapp" / "memory"
        mem_dir.mkdir(exist_ok=True)
        (mem_dir / "MEMORY.md").write_text("api_key = AKIAIOSFODNN7EXAMPLE\n")
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results = cs.scan_targets(targets, patterns)
        output = cs.format_scan_report(results, verbose=False, targets=targets)
        self.assertIn("Memory", output)

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
        self.assertIn("matches found", output.lower())
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
        self.assertRegex(output, r"\d+ match")

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

        results = {"sessions": {}, "indexes": {}, "history": {}, "paste_cache": {}, "file_history": {}, "ccrider": {}}
        summary = {"sessions": 5, "indexes": 2, "history": 1, "paste_cache": 0, "file_history": 0, "ccrider": 0}
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
        results = {
            "sessions": {fake_path: [("AWS Key", "AKIA...", 1, "specific")]},
            "indexes": {},
            "history": {},
            "paste_cache": {},
            "file_history": {},
            "ccrider": {},
        }
        summary = {"sessions": 1, "indexes": 0, "history": 0, "paste_cache": 0, "file_history": 0, "ccrider": 0}
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_scan_totals(results, summary)
        output = buf.getvalue()
        self.assertIn("rotated", output)

    def test_totals_no_rotation_warning_when_clean(self):
        """print_scan_totals should not warn about rotation when no secrets found."""
        import io
        from contextlib import redirect_stdout

        results = {"sessions": {}, "indexes": {}, "history": {}, "paste_cache": {}, "file_history": {}, "ccrider": {}}
        summary = {"sessions": 5, "indexes": 0, "history": 0, "paste_cache": 0, "file_history": 0, "ccrider": 0}
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_scan_totals(results, summary)
        output = buf.getvalue()
        self.assertNotIn("rotated", output)

    def test_totals_without_elapsed_time(self):
        """print_scan_totals should not show timing when elapsed is None."""
        import io
        from contextlib import redirect_stdout

        results = {"sessions": {}, "indexes": {}, "history": {}, "paste_cache": {}, "file_history": {}, "ccrider": {}}
        summary = {"sessions": 5, "indexes": 2, "history": 1, "paste_cache": 0, "file_history": 0, "ccrider": 0}
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
        self.secret_file.write_text('{"message":"key is AKIAIOSFODNN7EXAMPLE here"}\n{"message":"clean line"}\n')

        self.history = self.claude_dir / "history.jsonl"
        self.history.write_text('{"prompt":"token=ghp_ABCDEFghijklmnopqrst1234567890ab"}\n')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_scrub_replaces_secrets_in_files(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        cs.scrub_targets(targets, patterns)
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

    def test_filter_includes_memory_by_default(self):
        mem_dir = self.claude_dir / "projects" / "-Users-test-Code-myapp" / "memory"
        mem_dir.mkdir(exist_ok=True)
        (mem_dir / "MEMORY.md").write_text("api_key = AKIAIOSFODNN7EXAMPLE")
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        filtered = cs.filter_scrub_targets(targets, include="")
        self.assertEqual(len(filtered["memory"]), 1)

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

    def test_filter_warns_on_unknown_include_category(self):
        import io
        from contextlib import redirect_stderr

        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        buf = io.StringIO()
        with redirect_stderr(buf):
            cs.filter_scrub_targets(targets, include="paste-cache,bogus-category")
        self.assertIn("bogus-category", buf.getvalue())

    def test_scrub_idempotent(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        cs.scrub_targets(targets, patterns)
        content_after_first = self.secret_file.read_text()

        targets2 = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        cs.scrub_targets(targets2, patterns)
        content_after_second = self.secret_file.read_text()

        self.assertEqual(content_after_first, content_after_second)

    def test_scrub_uses_atomic_write(self):
        """Scrub should write to temp file then rename, not write in-place."""
        import unittest.mock

        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        with unittest.mock.patch("os.replace") as mock_replace:
            cs.scrub_targets(targets, patterns)
            # os.replace should have been called for files that had secrets
            self.assertGreater(mock_replace.call_count, 0)

    def test_scrub_skips_unreadable_files(self):
        """scrub_targets should skip files it can't read without crashing."""
        patterns = cs.get_builtin_patterns()
        unreadable = self.claude_dir / "projects" / "-Users-test-Code-myapp" / "unreadable.jsonl"
        unreadable.write_text('{"message":"AKIAIOSFODNN7EXAMPLE"}')
        unreadable.chmod(0o000)
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        stats = cs.scrub_targets(targets, patterns)
        self.assertIsInstance(stats, dict)
        unreadable.chmod(0o644)


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
            "[[patterns]]\n"
            'name = "Internal Key"\n'
            'regex = "myco_[a-zA-Z0-9]{32}"\n'
            "\n"
            "[[patterns]]\n"
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
        config.write_text('[[patterns]]\nname = "Internal Key"\nregex = "myco_[a-zA-Z0-9]{32}"\n')
        custom = cs.load_custom_patterns(config)
        text = "key=myco_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef"
        matches = cs.find_secrets(text, custom)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][0], "Internal Key")

    def test_invalid_regex_skipped(self):
        config = self.config_dir / "config.toml"
        config.write_text(
            "[[patterns]]\n"
            'name = "Bad Regex"\n'
            'regex = "[invalid(("\n'
            "\n"
            "[[patterns]]\n"
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
            "[[rules]]\n"
            'id = "aws-access-key"\n'
            'description = "AWS Access Key"\n'
            'regex = "(?:AKIA|ASIA)[0-9A-Z]{16}"\n'
            "\n"
            "[[rules]]\n"
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
        gitleaks_toml = '[[rules]]\nid = "bad"\ndescription = "Bad Pattern"\nregex = "[invalid((regex"\n'
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

    def test_entropy_at_exact_threshold(self):
        """Verify ENTROPY_THRESHOLD value and behavior below threshold."""
        threshold = cs.ENTROPY_THRESHOLD
        self.assertEqual(threshold, 3.8)
        val = "aAbBcCdD"  # 3.0 bits — below threshold
        self.assertLess(cs.entropy(val), threshold)


class TestLuhnCheck(unittest.TestCase):
    def test_valid_visa(self):
        self.assertTrue(cs.luhn_check("4111111111111111"))

    def test_valid_mastercard(self):
        self.assertTrue(cs.luhn_check("5500000000000004"))

    def test_valid_amex(self):
        self.assertTrue(cs.luhn_check("340000000000009"))

    def test_invalid_number(self):
        self.assertFalse(cs.luhn_check("1234567890123456"))

    def test_with_spaces(self):
        """Should work after stripping non-digits."""
        self.assertTrue(cs.luhn_check("4111 1111 1111 1111"))

    def test_with_dashes(self):
        self.assertTrue(cs.luhn_check("4111-1111-1111-1111"))

    def test_short_number(self):
        self.assertFalse(cs.luhn_check("411111"))

    def test_credit_card_pattern_finds_valid_cards(self):
        """The credit card pattern should detect Luhn-valid card numbers in text."""
        text = "card on file: 4111 1111 1111 1111 thanks"
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        names = [m[0] for m in matches]
        self.assertIn("Credit Card Number", names)

    def test_credit_card_pattern_skips_invalid_luhn(self):
        """Card-shaped numbers that fail Luhn should not match."""
        text = "order number: 4111 1111 1111 1112"
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        names = [m[0] for m in matches]
        self.assertNotIn("Credit Card Number", names)


class TestPatternTiers(unittest.TestCase):
    def test_generic_patterns_set_only_contains_generic_secret(self):
        """Only Generic Secret Assignment should be in the generic tier."""
        self.assertEqual(cs.GENERIC_PATTERNS, {"Generic Secret Assignment"})

    def test_narrowed_generic_does_not_match_bare_key(self):
        """'key=something' should no longer match generic pattern."""
        text = "key=myConfigSetting123"
        patterns = [p for p in cs.get_builtin_patterns() if p["name"] == "Generic Secret Assignment"]
        matches = cs.find_secrets(text, patterns)
        self.assertEqual(len(matches), 0)

    def test_narrowed_generic_does_not_match_bare_token(self):
        """'token=something' should no longer match generic pattern."""
        text = "token=development_value"
        patterns = [p for p in cs.get_builtin_patterns() if p["name"] == "Generic Secret Assignment"]
        matches = cs.find_secrets(text, patterns)
        self.assertEqual(len(matches), 0)

    def test_narrowed_generic_still_matches_password(self):
        """'password=something' should still match."""
        text = "password=mysecretpassword123"
        patterns = [p for p in cs.get_builtin_patterns() if p["name"] == "Generic Secret Assignment"]
        matches = cs.find_secrets(text, patterns)
        self.assertEqual(len(matches), 1)

    def test_narrowed_generic_still_matches_api_key(self):
        """'api_key=something' should still match."""
        text = "api_key=abc123def456ghi7"
        patterns = [p for p in cs.get_builtin_patterns() if p["name"] == "Generic Secret Assignment"]
        matches = cs.find_secrets(text, patterns)
        self.assertEqual(len(matches), 1)

    def test_narrowed_generic_matches_secret_key(self):
        """'secret_key=something' should match."""
        text = "secret_key=abc123def456ghi7"
        patterns = [p for p in cs.get_builtin_patterns() if p["name"] == "Generic Secret Assignment"]
        matches = cs.find_secrets(text, patterns)
        self.assertEqual(len(matches), 1)

    def test_patterns_have_tier_field(self):
        """All patterns should have a 'tier' field."""
        for p in cs.get_builtin_patterns():
            self.assertIn("tier", p, f"Pattern '{p['name']}' missing 'tier' field")
            self.assertIn(p["tier"], ("specific", "generic"))

    def test_only_generic_secret_assignment_is_generic_tier(self):
        """Only one pattern should have tier='generic'."""
        generic = [p for p in cs.get_builtin_patterns() if p["tier"] == "generic"]
        self.assertEqual(len(generic), 1)
        self.assertEqual(generic[0]["name"], "Generic Secret Assignment")


class TestFindSecretsTier(unittest.TestCase):
    def test_find_secrets_returns_4_tuples(self):
        """find_secrets should return (name, match_text, line_num, tier)."""
        text = "key is AKIAIOSFODNN7EXAMPLE"
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        self.assertGreater(len(matches), 0)
        self.assertEqual(len(matches[0]), 4)
        name, match_text, line_num, tier = matches[0]
        self.assertEqual(tier, "specific")

    def test_generic_match_returns_generic_tier(self):
        """Generic Secret Assignment matches should have tier='generic'."""
        text = "password=someplaintextvalue1"
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        generic_matches = [m for m in matches if m[0] == "Generic Secret Assignment"]
        self.assertGreater(len(generic_matches), 0)
        self.assertEqual(generic_matches[0][3], "generic")

    def test_high_entropy_generic_promoted_to_specific(self):
        """Generic match with high-entropy value should be promoted to 'specific'."""
        text = "api_key=sK3j8fAx7mNp2qRwL9"
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        generic_matches = [m for m in matches if m[0] == "Generic Secret Assignment"]
        self.assertGreater(len(generic_matches), 0)
        self.assertEqual(generic_matches[0][3], "specific")

    def test_low_entropy_generic_stays_generic(self):
        """Generic match with low-entropy value should stay 'generic'."""
        text = "password=development_mode"
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        generic_matches = [m for m in matches if m[0] == "Generic Secret Assignment"]
        self.assertGreater(len(generic_matches), 0)
        self.assertEqual(generic_matches[0][3], "generic")


class TestEndToEnd(unittest.TestCase):
    """End-to-end test: scan finds secrets, scrub removes them, re-scan finds none."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.claude_dir = Path(self.tmpdir) / ".claude"
        self.no_ccrider = Path(self.tmpdir) / "no-ccrider.db"
        proj = self.claude_dir / "projects" / "-Users-test-Code-app"
        proj.mkdir(parents=True)

        (proj / "session1.jsonl").write_text(
            '{"message":"AWS key: AKIAIOSFODNN7EXAMPLE"}\n{"message":"Stripe: sk_live_abcdefghij1234567890"}\n'
        )
        (proj / "session2.jsonl").write_text('{"message":"no secrets here"}\n')

        (self.claude_dir / "history.jsonl").write_text('{"prompt":"ghp_ABCDEFghijklmnopqrst1234567890ab"}\n')

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
        initial_count = sum(len(m) for cat in results.values() for m in cat.values())
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
        final_count = sum(len(m) for cat in results4.values() for m in cat.values())
        self.assertEqual(final_count, 0)


class TestTieredScrub(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.claude_dir = Path(self.tmpdir) / ".claude"
        self.no_ccrider = Path(self.tmpdir) / "no-ccrider.db"
        proj = self.claude_dir / "projects" / "-Users-test-Code-myapp"
        proj.mkdir(parents=True)
        self.secret_file = proj / "session.jsonl"

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_default_scrub_keeps_generic_matches(self):
        """Default scrub should NOT redact low-entropy generic matches."""
        self.secret_file.write_text('{"message":"password=development_mode and AKIAIOSFODNN7EXAMPLE"}\n')
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        cs.scrub_targets(targets, patterns)
        content = self.secret_file.read_text()
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", content, "Specific match should be scrubbed")
        self.assertIn("development_mode", content, "Low-entropy generic should be preserved")

    def test_aggressive_scrub_removes_generic_matches(self):
        """--aggressive should redact generic matches too."""
        self.secret_file.write_text('{"message":"password=development_mode here"}\n')
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        cs.scrub_targets(targets, patterns, aggressive=True)
        content = self.secret_file.read_text()
        self.assertNotIn("development_mode", content, "Aggressive should scrub generic")
        self.assertIn("[REDACTED:", content)

    def test_high_entropy_generic_scrubbed_by_default(self):
        """High-entropy generic match should be scrubbed even without --aggressive."""
        self.secret_file.write_text('{"message":"api_key=sK3j8fAx7mNp2qRwL9vB"}\n')
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        cs.scrub_targets(targets, patterns)
        content = self.secret_file.read_text()
        self.assertNotIn("sK3j8fAx7mNp2qRwL9vB", content, "High-entropy generic should be scrubbed")

    def test_aggressive_flag_parses(self):
        args = cs.parse_args(["scrub", "--aggressive"])
        self.assertTrue(args.aggressive)

    def test_aggressive_default_false(self):
        args = cs.parse_args(["scrub"])
        self.assertFalse(args.aggressive)


class TestScanTierOutput(unittest.TestCase):
    def test_scan_totals_shows_tier_breakdown(self):
        """print_scan_totals should split counts by tier."""
        import io
        from contextlib import redirect_stdout

        fake_path = Path("/tmp/fake.jsonl")
        results = {
            "sessions": {
                fake_path: [
                    ("AWS Key", "AKIA...", 1, "specific"),
                    ("Generic Secret Assignment", "password=dev_mode_val", 2, "generic"),
                ]
            },
            "indexes": {},
            "history": {},
            "paste_cache": {},
            "file_history": {},
            "ccrider": {},
        }
        summary = {"sessions": 1, "indexes": 0, "history": 0, "paste_cache": 0, "file_history": 0, "ccrider": 0}
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_scan_totals(results, summary)
        output = buf.getvalue()
        self.assertIn("Secrets:", output)
        self.assertIn("Generic:", output)

    def test_scan_totals_says_matches(self):
        """Total line should say 'matches' not 'secrets'."""
        import io
        from contextlib import redirect_stdout

        fake_path = Path("/tmp/fake.jsonl")
        results = {
            "sessions": {fake_path: [("AWS Key", "AKIA...", 1, "specific")]},
            "indexes": {},
            "history": {},
            "paste_cache": {},
            "file_history": {},
            "ccrider": {},
        }
        summary = {"sessions": 1, "indexes": 0, "history": 0, "paste_cache": 0, "file_history": 0, "ccrider": 0}
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_scan_totals(results, summary)
        output = buf.getvalue()
        # The total line should use "match" or "matches"
        self.assertIn("match", output)

    def test_scan_totals_hides_generic_when_zero(self):
        """Generic line should not appear when there are no generic matches."""
        import io
        from contextlib import redirect_stdout

        fake_path = Path("/tmp/fake.jsonl")
        results = {
            "sessions": {fake_path: [("AWS Key", "AKIA...", 1, "specific")]},
            "indexes": {},
            "history": {},
            "paste_cache": {},
            "file_history": {},
            "ccrider": {},
        }
        summary = {"sessions": 1, "indexes": 0, "history": 0, "paste_cache": 0, "file_history": 0, "ccrider": 0}
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_scan_totals(results, summary)
        output = buf.getvalue()
        self.assertNotIn("Generic:", output)

    def test_progress_says_matches(self):
        """Progress lines should say 'matches' not 'secrets'."""
        import io
        from contextlib import redirect_stdout

        tmpdir = tempfile.mkdtemp()
        claude_dir = Path(tmpdir) / ".claude"
        proj = claude_dir / "projects" / "-test"
        proj.mkdir(parents=True)
        (proj / "s.jsonl").write_text('{"m":"AKIAIOSFODNN7EXAMPLE"}\n')
        no_db = Path(tmpdir) / "no.db"
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(claude_dir, ccrider_db=no_db)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.scan_targets(targets, patterns, show_progress=True)
        output = buf.getvalue()
        # Final summary lines should use "match" or "matches"
        lines = [line for line in output.split("\n") if "found" in line]
        for line in lines:
            self.assertIn("match", line.lower())
        shutil.rmtree(tmpdir)

    def test_verbose_detail_shows_tier_tag(self):
        """Verbose output should tag generic matches with [generic]."""
        import io
        from contextlib import redirect_stdout

        fake_path = Path("/tmp/fake.jsonl")
        results = {
            "sessions": {
                fake_path: [
                    ("AWS Key", "AKIA...", 1, "specific"),
                    ("Generic Secret Assignment", "password=dev_mode_val", 2, "generic"),
                ]
            },
            "indexes": {},
            "history": {},
            "paste_cache": {},
            "file_history": {},
            "ccrider": {},
        }
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_verbose_detail(results)
        output = buf.getvalue()
        self.assertIn("[generic]", output.lower())

    def test_verbose_detail_no_tag_for_specific(self):
        """Verbose output should NOT tag specific matches with [specific]."""
        import io
        from contextlib import redirect_stdout

        fake_path = Path("/tmp/fake.jsonl")
        results = {
            "sessions": {
                fake_path: [
                    ("AWS Key", "AKIA...", 1, "specific"),
                ]
            },
            "indexes": {},
            "history": {},
            "paste_cache": {},
            "file_history": {},
            "ccrider": {},
        }
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_verbose_detail(results)
        output = buf.getvalue()
        self.assertNotIn("[specific]", output.lower())
        self.assertNotIn("[generic]", output.lower())


# ---------------------------------------------------------------------------
# Rotation list
# ---------------------------------------------------------------------------


class TestRotationList(unittest.TestCase):
    """Tests for build_rotation_list() which summarizes secrets for rotation."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.claude_dir = self.tmpdir / ".claude"
        proj = self.claude_dir / "projects" / "-Users-test-Code-myapp"
        proj.mkdir(parents=True)
        self.session_file = proj / "abc123.jsonl"
        self.session_file.write_text('{"message":"my key is AKIAIOSFODNN7EXAMPLE"}\n')
        self.history_file = self.claude_dir / "history.jsonl"
        self.history_file.write_text('{"prompt":"ghp_ABCDEFghijklmnopqrst1234567890ab"}\n')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_returns_list_of_dicts(self):
        results = {
            "sessions": {
                self.session_file: [
                    ("AWS Access Key", "AKIAIOSFODNN7EXAMPLE", 1, "specific"),
                ]
            },
            "history": {},
            "indexes": {},
            "paste_cache": {},
            "file_history": {},
            "memory": {},
            "ccrider": {},
        }
        rotation = cs.build_rotation_list(results)
        self.assertIsInstance(rotation, list)
        self.assertTrue(all(isinstance(r, dict) for r in rotation))

    def test_contains_pattern_name_and_count(self):
        results = {
            "sessions": {
                self.session_file: [
                    ("AWS Access Key", "AKIAIOSFODNN7EXAMPLE", 1, "specific"),
                    ("AWS Access Key", "AKIAIOSFODNN7EXAMPLE", 5, "specific"),
                ]
            },
            "history": {},
            "indexes": {},
            "paste_cache": {},
            "file_history": {},
            "memory": {},
            "ccrider": {},
        }
        rotation = cs.build_rotation_list(results)
        aws_entry = [r for r in rotation if r["name"] == "AWS Access Key"]
        self.assertEqual(len(aws_entry), 1)
        self.assertEqual(aws_entry[0]["count"], 2)

    def test_includes_earliest_and_latest_dates(self):
        results = {
            "sessions": {
                self.session_file: [
                    ("AWS Access Key", "AKIAIOSFODNN7EXAMPLE", 1, "specific"),
                ]
            },
            "history": {
                self.history_file: [
                    ("GitHub Token", "ghp_ABCDEFghijklmnopqrst1234567890ab", 1, "specific"),
                ]
            },
            "indexes": {},
            "paste_cache": {},
            "file_history": {},
            "memory": {},
            "ccrider": {},
        }
        rotation = cs.build_rotation_list(results)
        for entry in rotation:
            self.assertIn("earliest", entry)
            self.assertIn("latest", entry)
            # Dates should be ISO-ish strings (YYYY-MM-DD)
            self.assertRegex(entry["earliest"], r"\d{4}-\d{2}-\d{2}")
            self.assertRegex(entry["latest"], r"\d{4}-\d{2}-\d{2}")

    def test_multiple_secret_types(self):
        results = {
            "sessions": {
                self.session_file: [
                    ("AWS Access Key", "AKIAIOSFODNN7EXAMPLE", 1, "specific"),
                    ("Stripe Key", "sk_live_abc123", 2, "specific"),
                ]
            },
            "history": {},
            "indexes": {},
            "paste_cache": {},
            "file_history": {},
            "memory": {},
            "ccrider": {},
        }
        rotation = cs.build_rotation_list(results)
        names = {r["name"] for r in rotation}
        self.assertEqual(names, {"AWS Access Key", "Stripe Key"})

    def test_empty_results_returns_empty_list(self):
        results = {
            "sessions": {},
            "history": {},
            "indexes": {},
            "paste_cache": {},
            "file_history": {},
            "memory": {},
            "ccrider": {},
        }
        rotation = cs.build_rotation_list(results)
        self.assertEqual(rotation, [])

    def test_sorted_by_count_descending(self):
        results = {
            "sessions": {
                self.session_file: [
                    ("Stripe Key", "sk_live_abc", 1, "specific"),
                    ("AWS Access Key", "AKIA...", 2, "specific"),
                    ("AWS Access Key", "AKIA...", 3, "specific"),
                    ("AWS Access Key", "AKIA...", 5, "specific"),
                ]
            },
            "history": {},
            "indexes": {},
            "paste_cache": {},
            "file_history": {},
            "memory": {},
            "ccrider": {},
        }
        rotation = cs.build_rotation_list(results)
        self.assertEqual(rotation[0]["name"], "AWS Access Key")
        self.assertEqual(rotation[1]["name"], "Stripe Key")


class TestFormatRotationList(unittest.TestCase):
    """Tests for format_rotation_list() text output."""

    def test_formats_readable_output(self):
        rotation = [
            {"name": "AWS Access Key", "count": 3, "earliest": "2026-03-01", "latest": "2026-03-08"},
            {"name": "GitHub Token", "count": 1, "earliest": "2026-03-05", "latest": "2026-03-05"},
        ]
        output = cs.format_rotation_list(rotation)
        self.assertIn("AWS Access Key", output)
        self.assertIn("GitHub Token", output)
        self.assertIn("2026-03-01", output)
        self.assertIn("2026-03-08", output)

    def test_empty_list_returns_no_action_message(self):
        output = cs.format_rotation_list([])
        self.assertIn("no credentials", output.lower())


class TestSaveRotationList(unittest.TestCase):
    """Tests for save_rotation_list() which persists the checklist to disk."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.rotation = [
            {"name": "AWS Access Key", "count": 3, "earliest": "2026-03-01", "latest": "2026-03-08"},
            {"name": "GitHub Token", "count": 1, "earliest": "2026-03-05", "latest": "2026-03-05"},
        ]

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_saves_text_format(self):
        path = cs.save_rotation_list(self.rotation, fmt="text", config_dir=self.tmpdir)
        self.assertTrue(path.exists())
        self.assertEqual(path.suffix, ".txt")
        content = path.read_text()
        self.assertIn("AWS Access Key", content)
        self.assertIn("GitHub Token", content)

    def test_saves_json_format(self):
        path = cs.save_rotation_list(self.rotation, fmt="json", config_dir=self.tmpdir)
        self.assertTrue(path.exists())
        self.assertEqual(path.suffix, ".json")
        import json

        data = json.loads(path.read_text())
        creds = data["credentials"]
        self.assertEqual(len(creds), 2)
        self.assertEqual(creds[0]["name"], "AWS Access Key")

    def test_creates_config_dir_if_missing(self):
        nested = self.tmpdir / "sub" / "dir"
        path = cs.save_rotation_list(self.rotation, fmt="text", config_dir=nested)
        self.assertTrue(nested.is_dir())
        self.assertTrue(path.exists())

    def test_json_includes_generated_timestamp(self):
        import json

        path = cs.save_rotation_list(self.rotation, fmt="json", config_dir=self.tmpdir)
        data = json.loads(path.read_text())
        self.assertIn("generated_at", data)
        self.assertIn("credentials", data)


# ---------------------------------------------------------------------------
# Stats command
# ---------------------------------------------------------------------------


class TestGatherStats(unittest.TestCase):
    """Tests for gather_stats() which mines session JSONL files for usage data."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.projects_dir = self.tmpdir / "projects"
        self.projects_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_session(self, project_name, session_id, lines):
        """Helper to write a JSONL session file with the given JSON lines."""
        import json

        pdir = self.projects_dir / project_name
        pdir.mkdir(exist_ok=True)
        fpath = pdir / f"{session_id}.jsonl"
        with open(fpath, "w") as f:
            for entry in lines:
                f.write(json.dumps(entry) + "\n")
        return fpath

    def test_gather_stats_empty_dir(self):
        """Returns zero counts when no session files exist."""
        stats = cs.gather_stats(self.tmpdir)
        self.assertEqual(stats["total_sessions"], 0)
        self.assertEqual(stats["total_user_messages"], 0)
        self.assertEqual(stats["total_assistant_messages"], 0)
        self.assertEqual(stats["total_projects"], 0)

    def test_gather_stats_counts_messages(self):
        """Counts user and assistant messages from JSONL entries."""
        self._write_session(
            "proj1",
            "abc",
            [
                {"type": "user", "timestamp": "2026-01-15T10:00:00Z"},
                {"type": "assistant", "timestamp": "2026-01-15T10:00:01Z"},
                {"type": "assistant", "timestamp": "2026-01-15T10:00:02Z"},
                {"type": "user", "timestamp": "2026-01-15T10:00:03Z"},
                {"type": "progress"},  # not counted
            ],
        )
        stats = cs.gather_stats(self.tmpdir)
        self.assertEqual(stats["total_sessions"], 1)
        self.assertEqual(stats["total_user_messages"], 2)
        self.assertEqual(stats["total_assistant_messages"], 2)

    def test_gather_stats_multiple_projects(self):
        """Counts sessions and projects across multiple project dirs."""
        self._write_session(
            "proj1",
            "s1",
            [
                {"type": "user", "timestamp": "2026-01-15T10:00:00Z"},
                {"type": "assistant", "timestamp": "2026-01-15T10:00:01Z"},
            ],
        )
        self._write_session(
            "proj1",
            "s2",
            [
                {"type": "user", "timestamp": "2026-02-01T10:00:00Z"},
            ],
        )
        self._write_session(
            "proj2",
            "s3",
            [
                {"type": "user", "timestamp": "2026-03-01T10:00:00Z"},
                {"type": "assistant", "timestamp": "2026-03-01T10:00:01Z"},
            ],
        )
        stats = cs.gather_stats(self.tmpdir)
        self.assertEqual(stats["total_sessions"], 3)
        self.assertEqual(stats["total_projects"], 2)
        self.assertEqual(stats["total_user_messages"], 3)
        self.assertEqual(stats["total_assistant_messages"], 2)

    def test_gather_stats_finds_earliest_session(self):
        """Reports the earliest timestamp across all sessions."""
        self._write_session(
            "proj1",
            "old",
            [
                {"type": "user", "timestamp": "2025-06-14T08:00:00Z"},
            ],
        )
        self._write_session(
            "proj1",
            "new",
            [
                {"type": "user", "timestamp": "2026-03-01T10:00:00Z"},
            ],
        )
        stats = cs.gather_stats(self.tmpdir)
        self.assertEqual(stats["first_session_date"], "2025-06-14")

    def test_gather_stats_most_active_project(self):
        """Reports the project with the most sessions."""
        self._write_session("proj1", "s1", [{"type": "user", "timestamp": "2026-01-01T00:00:00Z"}])
        self._write_session("proj1", "s2", [{"type": "user", "timestamp": "2026-01-02T00:00:00Z"}])
        self._write_session("proj1", "s3", [{"type": "user", "timestamp": "2026-01-03T00:00:00Z"}])
        self._write_session("proj2", "s4", [{"type": "user", "timestamp": "2026-01-04T00:00:00Z"}])
        stats = cs.gather_stats(self.tmpdir)
        self.assertEqual(stats["most_active_project_sessions"], 3)
        self.assertIn("proj1", stats["most_active_project"])

    def test_gather_stats_biggest_file(self):
        """Reports the largest session file by size."""
        # Write a small session
        self._write_session(
            "proj1",
            "small",
            [
                {"type": "user", "timestamp": "2026-01-01T00:00:00Z"},
            ],
        )
        # Write a bigger session
        self._write_session(
            "proj1",
            "big",
            [
                {"type": "user", "timestamp": "2026-01-01T00:00:00Z", "message": {"content": "x" * 1000}},
                {"type": "assistant", "timestamp": "2026-01-01T00:00:01Z", "message": {"content": "y" * 2000}},
                {"type": "user", "timestamp": "2026-01-01T00:00:02Z", "message": {"content": "z" * 1500}},
            ],
        )
        stats = cs.gather_stats(self.tmpdir)
        self.assertIn("big", stats["biggest_file_name"])
        self.assertGreater(stats["biggest_file_size"], 0)

    def test_gather_stats_disk_usage(self):
        """Reports total disk usage of the claude dir."""
        self._write_session(
            "proj1",
            "s1",
            [
                {"type": "user", "timestamp": "2026-01-01T00:00:00Z", "message": {"content": "hello"}},
            ],
        )
        stats = cs.gather_stats(self.tmpdir)
        self.assertGreater(stats["disk_usage_bytes"], 0)

    def test_gather_stats_biggest_file_messages(self):
        """Reports message count for the biggest session file."""
        self._write_session(
            "proj1",
            "big",
            [
                {"type": "user", "timestamp": "2026-01-01T00:00:00Z"},
                {"type": "assistant", "timestamp": "2026-01-01T00:00:01Z"},
                {"type": "user", "timestamp": "2026-01-01T00:00:02Z"},
                {"type": "assistant", "timestamp": "2026-01-01T00:00:03Z"},
            ],
        )
        stats = cs.gather_stats(self.tmpdir)
        self.assertEqual(stats["biggest_file_messages"], 4)


class TestFormatStats(unittest.TestCase):
    """Tests for format_stats() which renders stats into display text."""

    def _sample_stats(self):
        return {
            "total_sessions": 142,
            "total_projects": 11,
            "total_user_messages": 2103,
            "total_assistant_messages": 2788,
            "first_session_date": "2025-06-14",
            "disk_usage_bytes": 888_000_000,
            "most_active_project": "~/Code/regrade3",
            "most_active_project_sessions": 34,
            "most_active_project_messages": 1204,
            "biggest_file_name": "regrade3/abc123.jsonl",
            "biggest_file_size": 14_900_000,
            "biggest_file_messages": 2847,
        }

    def test_format_stats_includes_session_count(self):
        output = cs.format_stats(self._sample_stats())
        self.assertIn("142", output)
        self.assertIn("11 projects", output)

    def test_format_stats_includes_message_counts(self):
        output = cs.format_stats(self._sample_stats())
        self.assertIn("2,103", output)
        self.assertIn("2,788", output)

    def test_format_stats_includes_first_session_date(self):
        output = cs.format_stats(self._sample_stats())
        self.assertIn("2025-06-14", output)

    def test_format_stats_includes_disk_usage(self):
        output = cs.format_stats(self._sample_stats())
        # 888 MB
        self.assertIn("MB", output)

    def test_format_stats_includes_most_active(self):
        output = cs.format_stats(self._sample_stats())
        self.assertIn("regrade3", output)
        self.assertIn("34 sessions", output)

    def test_format_stats_includes_biggest_file(self):
        output = cs.format_stats(self._sample_stats())
        self.assertIn("abc123", output)

    def test_format_stats_handles_zero_sessions(self):
        """Gracefully handles empty data."""
        stats = {
            "total_sessions": 0,
            "total_projects": 0,
            "total_user_messages": 0,
            "total_assistant_messages": 0,
            "first_session_date": None,
            "disk_usage_bytes": 0,
            "most_active_project": None,
            "most_active_project_sessions": 0,
            "most_active_project_messages": 0,
            "biggest_file_name": None,
            "biggest_file_size": 0,
            "biggest_file_messages": 0,
        }
        output = cs.format_stats(stats)
        self.assertIn("0", output)
        # Should not crash


# ---------------------------------------------------------------------------
# Secure delete
# ---------------------------------------------------------------------------


class TestSecureDelete(unittest.TestCase):
    """Tests for secure_delete() which overwrites files before unlinking."""

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
        import unittest.mock

        with unittest.mock.patch.object(Path, "unlink") as mock_unlink:
            cs.secure_delete(f)
            self.assertEqual(f.read_bytes(), b"\x00" * original_size)
            mock_unlink.assert_called_once()

    def test_secure_delete_returns_false_on_missing_file(self):
        f = self.tmpdir / "nonexistent.txt"
        result = cs.secure_delete(f)
        self.assertIs(result, False)

    def test_secure_delete_returns_false_on_permission_error(self):
        f = self.tmpdir / "readonly.txt"
        f.write_text("secret")
        f.chmod(0o000)
        result = cs.secure_delete(f)
        self.assertIs(result, False)
        f.chmod(0o644)

    def test_secure_delete_warns_on_failure(self):
        """Failed secure delete should print a warning to stderr."""
        import io
        from contextlib import redirect_stderr

        f = self.tmpdir / "nonexistent.txt"
        buf = io.StringIO()
        with redirect_stderr(buf):
            cs.secure_delete(f)
        output = buf.getvalue()
        self.assertIn("Warning", output)
        self.assertIn("secure delete failed", output)


class TestDownloadPatternsDB(unittest.TestCase):
    """Tests for download_patterns_db error handling."""

    def test_download_catches_url_errors_not_all_exceptions(self):
        """Verify we don't catch broad Exception."""
        import ast
        import inspect

        source = inspect.getsource(cs.download_patterns_db)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Should NOT catch bare Exception
                if node.type and isinstance(node.type, ast.Name):
                    self.assertNotEqual(
                        node.type.id, "Exception", "download_patterns_db should not catch bare Exception"
                    )


class TestStatsSubcommand(unittest.TestCase):
    """Tests for stats argparse integration."""

    def test_stats_subcommand_parses(self):
        args = cs.parse_args(["stats"])
        self.assertEqual(args.command, "stats")


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
        self.assertTrue(result.endswith("\u2026"))

    def test_shorten_project_path(self):
        home = str(Path.home())
        long_path = home + "/.claude/projects/-Users-test-Code-myapp/abc.jsonl"
        result = cs.shorten_project(long_path)
        self.assertTrue(result.startswith("~"))
        self.assertTrue(len(result) < len(long_path))

    def test_project_path_from_dir_name(self):
        result = cs.project_path_from_dir_name("-Users-test-Code-myapp")
        self.assertIn("/", result)


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
        cache_file = self.tmpdir / "test-cache.json"
        original_cache = cs.SCAN_CACHE_FILE
        cs.SCAN_CACHE_FILE = cache_file
        try:
            cs.save_scan_cache(results, targets)
            self.assertTrue(cache_file.exists())
            loaded_results, loaded_summary = cs.load_scan_cache()
            self.assertIsNotNone(loaded_results)
            self.assertEqual(set(loaded_results.keys()), set(results.keys()))
        finally:
            cs.SCAN_CACHE_FILE = original_cache

    def test_load_cache_skips_symlinked_paths(self):
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        results = cs.scan_targets(targets, patterns)
        cache_file = self.tmpdir / "test-cache.json"
        original_cache = cs.SCAN_CACHE_FILE
        cs.SCAN_CACHE_FILE = cache_file
        try:
            cs.save_scan_cache(results, targets)
            # Replace the secret file with a symlink
            sensitive = self.tmpdir / "sensitive.txt"
            sensitive.write_text("do not read")
            self.secret_file.unlink()
            self.secret_file.symlink_to(sensitive)
            loaded_results, _ = cs.load_scan_cache()
            # Symlinked file should be excluded from loaded results
            all_paths = []
            for cat_results in loaded_results.values():
                all_paths.extend(cat_results.keys())
            self.assertNotIn(self.secret_file, all_paths)
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


class TestExtractSession(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_extracts_metadata_from_jsonl(self):
        f = self.tmpdir / "abc123.jsonl"
        f.write_text(
            '{"type":"user","timestamp":"2026-03-01T10:00:00Z",'
            '"cwd":"/home/test","message":{"content":"hello world"}}\n'
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


class TestSymlinkProtection(unittest.TestCase):
    """Verify symlinks are skipped to prevent path traversal attacks."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.claude_dir = self.tmpdir / ".claude"
        self.no_ccrider = self.tmpdir / "nonexistent" / "sessions.db"
        proj = self.claude_dir / "projects" / "-Users-test-Code-myapp"
        proj.mkdir(parents=True)
        # Real file with a secret
        self.real_file = proj / "real.jsonl"
        self.real_file.write_text('{"message":"AKIAIOSFODNN7EXAMPLE"}\n')
        # Symlink to a sensitive file (contains a secret so scrub would try to modify it)
        self.sensitive = self.tmpdir / "sensitive.txt"
        self.sensitive.write_text('{"message":"AKIAIOSFODNN7EXAMPLE"}\n')
        self.symlink = proj / "evil.jsonl"
        self.symlink.symlink_to(self.sensitive)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_discover_targets_skips_symlinks(self):
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        all_files = []
        for files in targets.values():
            all_files.extend(files)
        # Real file should be included
        self.assertIn(self.real_file, all_files)
        # Symlink should NOT be included
        self.assertNotIn(self.symlink, all_files)

    def test_scrub_skips_symlinks(self):
        patterns = cs.get_builtin_patterns()
        # Force symlink into targets (bypass discover protection)
        targets = {"sessions": [self.symlink, self.real_file]}
        stats = cs.scrub_targets(targets, patterns)
        # Only the real file should be scrubbed (1 file), not the symlink
        self.assertEqual(stats["total_files"], 1)
        # Sensitive file should be untouched — content must not be redacted
        self.assertEqual(self.sensitive.read_text(), '{"message":"AKIAIOSFODNN7EXAMPLE"}\n')


class TestRegexSafety(unittest.TestCase):
    """Verify ReDoS-prone patterns are rejected."""

    def test_rejects_nested_quantifiers(self):
        """Patterns with nested quantifiers like (a+)+ should be rejected."""
        import io
        from contextlib import redirect_stderr

        tmpdir = Path(tempfile.mkdtemp())
        try:
            config_file = tmpdir / "config.toml"
            config_file.write_text('[[patterns]]\nname = "redos"\nregex = "(a+)+b"\n')
            buf = io.StringIO()
            with redirect_stderr(buf):
                patterns = cs.load_custom_patterns(config_file)
            # The ReDoS pattern should have been rejected
            names = [p["name"] for p in patterns]
            self.assertNotIn("redos", names)
            self.assertIn("nested quantifier", buf.getvalue().lower())
        finally:
            shutil.rmtree(tmpdir)

    def test_rejects_overly_long_patterns(self):
        """Patterns longer than 500 chars should be rejected."""
        import io
        from contextlib import redirect_stderr

        tmpdir = Path(tempfile.mkdtemp())
        try:
            config_file = tmpdir / "config.toml"
            long_regex = "a" * 501
            config_file.write_text(f'[[patterns]]\nname = "toolong"\nregex = "{long_regex}"\n')
            buf = io.StringIO()
            with redirect_stderr(buf):
                patterns = cs.load_custom_patterns(config_file)
            names = [p["name"] for p in patterns]
            self.assertNotIn("toolong", names)
            self.assertIn("too long", buf.getvalue().lower())
        finally:
            shutil.rmtree(tmpdir)

    def test_accepts_safe_patterns(self):
        """Normal patterns should still be accepted."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            config_file = tmpdir / "config.toml"
            config_file.write_text('[[patterns]]\nname = "safe"\nregex = "SAFE_[A-Za-z0-9]{20,}"\n')
            patterns = cs.load_custom_patterns(config_file)
            names = [p["name"] for p in patterns]
            self.assertIn("safe", names)
        finally:
            shutil.rmtree(tmpdir)

    def test_patterns_db_rejects_redos(self):
        """load_patterns_db should also reject ReDoS-prone patterns."""
        import io
        from contextlib import redirect_stderr

        tmpdir = Path(tempfile.mkdtemp())
        try:
            toml_file = tmpdir / "gitleaks.toml"
            toml_file.write_text('[[rules]]\nid = "redos-rule"\ndescription = "Bad Rule"\nregex = "(x+)+y"\n')
            buf = io.StringIO()
            with redirect_stderr(buf):
                patterns = cs.load_patterns_db(toml_file)
            names = [p["name"] for p in patterns]
            self.assertNotIn("Bad Rule", names)
        finally:
            shutil.rmtree(tmpdir)
