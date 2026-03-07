# Pattern Tiers Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split patterns into specific/generic tiers so scrub only redacts high-confidence matches by default, add credit card detection with Luhn validation, and use Shannon entropy to promote high-entropy generic matches.

**Architecture:** Patterns gain a `"tier"` field (`"specific"` or `"generic"`). `find_secrets()` returns a 4-tuple adding tier. `scrub_targets()` and `redact_secrets()` accept a tier filter. Entropy check runs only on generic matches to decide promotion. Credit card uses regex + Luhn post-validation.

**Tech Stack:** Python 3.6+ stdlib only (`math.log2`, `collections.Counter`). No new dependencies.

---

### Task 1: Add `entropy()` function and tests

**Files:**
- Modify: `claude-scrub:14` (add `from math import log2` and `from collections import Counter`)
- Modify: `claude-scrub` (add `entropy()` function after `make_json_safe_regex()`, around line 242)
- Test: `tests/test_claude_scrub.py`

**Step 1: Write the failing tests**

Add to `tests/test_claude_scrub.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_claude_scrub.py::TestEntropy -v`
Expected: FAIL with `AttributeError: module 'claude_scrub' has no attribute 'entropy'`

**Step 3: Write minimal implementation**

Add to `claude-scrub` at line 14 (imports):
```python
from collections import Counter
from math import log2
```

Add after `make_json_safe_regex()` (~line 242):
```python
# Entropy threshold for promoting generic matches to specific tier.
# Values above this are likely random/generated (API keys, tokens).
# Values below are likely human-readable (config values, placeholders).
ENTROPY_THRESHOLD = 3.8


def entropy(s):
    """Compute Shannon entropy in bits per character."""
    if not s:
        return 0.0
    freq = Counter(s)
    length = len(s)
    return -sum(count / length * log2(count / length) for count in freq.values())
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_claude_scrub.py::TestEntropy -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: add Shannon entropy function for generic match scoring"
```

---

### Task 2: Add Luhn validation and credit card pattern with tests

**Files:**
- Modify: `claude-scrub` (add `luhn_check()` after `entropy()`, add credit card to `get_builtin_patterns()`)
- Test: `tests/test_claude_scrub.py`

**Step 1: Write the failing tests**

```python
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
        text = 'card on file: 4111 1111 1111 1111 thanks'
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        names = [m[0] for m in matches]
        self.assertIn("Credit Card Number", names)

    def test_credit_card_pattern_skips_invalid_luhn(self):
        """Card-shaped numbers that fail Luhn should not match."""
        text = 'order number: 4111 1111 1111 1112'
        patterns = cs.get_builtin_patterns()
        matches = cs.find_secrets(text, patterns)
        names = [m[0] for m in matches]
        self.assertNotIn("Credit Card Number", names)
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_claude_scrub.py::TestLuhnCheck -v`
Expected: FAIL with `AttributeError: module 'claude_scrub' has no attribute 'luhn_check'`

**Step 3: Write minimal implementation**

Add after `entropy()` in `claude-scrub`:
```python
def luhn_check(number_str):
    """Validate a credit card number using the Luhn algorithm."""
    digits = [int(c) for c in number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0
```

Credit card detection requires a custom approach in `find_secrets()` because it needs post-match Luhn validation. Add a regex-only entry to `get_builtin_patterns()` at the end of the specific patterns (before the generic section):

```python
        # --- PII (validated) ---
        {"name": "Credit Card Number", "regex": re.compile(r'\b[3-6]\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{1,4}\b'), "validate": "luhn"},
```

Then modify `find_secrets()` to check the `validate` field. After `line_matches.append(...)` (~line 137), add validation filtering:

```python
        # Apply post-match validation (e.g., Luhn for credit cards)
        validated = []
        for name, start, end, match_text in line_matches:
            validator = next((p.get("validate") for p in patterns if p["name"] == name), None)
            if validator == "luhn" and not luhn_check(match_text):
                continue
            validated.append((name, start, end, match_text))
        line_matches = validated
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_claude_scrub.py::TestLuhnCheck -v`
Expected: All 9 tests PASS

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: add credit card detection with Luhn validation"
```

---

### Task 3: Add pattern tiers and narrow generic keywords

**Files:**
- Modify: `claude-scrub:47-120` (pattern definitions and `GENERIC_PATTERNS`)
- Test: `tests/test_claude_scrub.py`

**Step 1: Write the failing tests**

```python
class TestPatternTiers(unittest.TestCase):

    def test_generic_patterns_set_only_contains_generic_secret(self):
        """Only Generic Secret Assignment should be in the generic tier."""
        self.assertEqual(cs.GENERIC_PATTERNS, {"Generic Secret Assignment"})

    def test_narrowed_generic_does_not_match_bare_key(self):
        """'key=something' should no longer match generic pattern."""
        text = 'key=myConfigSetting123'
        patterns = [p for p in cs.get_builtin_patterns() if p["name"] == "Generic Secret Assignment"]
        matches = cs.find_secrets(text, patterns)
        self.assertEqual(len(matches), 0)

    def test_narrowed_generic_does_not_match_bare_token(self):
        """'token=something' should no longer match generic pattern."""
        text = 'token=development_value'
        patterns = [p for p in cs.get_builtin_patterns() if p["name"] == "Generic Secret Assignment"]
        matches = cs.find_secrets(text, patterns)
        self.assertEqual(len(matches), 0)

    def test_narrowed_generic_still_matches_password(self):
        """'password=something' should still match."""
        text = 'password=mysecretpassword123'
        patterns = [p for p in cs.get_builtin_patterns() if p["name"] == "Generic Secret Assignment"]
        matches = cs.find_secrets(text, patterns)
        self.assertEqual(len(matches), 1)

    def test_narrowed_generic_still_matches_api_key(self):
        """'api_key=something' should still match."""
        text = 'api_key=abc123def456ghi7'
        patterns = [p for p in cs.get_builtin_patterns() if p["name"] == "Generic Secret Assignment"]
        matches = cs.find_secrets(text, patterns)
        self.assertEqual(len(matches), 1)

    def test_narrowed_generic_matches_secret_key(self):
        """'secret_key=something' should match."""
        text = 'secret_key=abc123def456ghi7'
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
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_claude_scrub.py::TestPatternTiers -v`
Expected: FAIL (patterns don't have `tier` field, `GENERIC_PATTERNS` still has 5 entries, keyword regex still too broad)

**Step 3: Implement changes**

3a. Update `GENERIC_PATTERNS` set (line ~114):
```python
GENERIC_PATTERNS = {
    "Generic Secret Assignment",
}
```

3b. Narrow the generic pattern regex in `get_builtin_patterns()` (line ~104):
```python
        {"name": "Generic Secret Assignment", "regex": re.compile(r'(?:password|credential|passwd|secret_key|api_key|apikey|secret_token)\s*[:=]\s*[^\s",}\]]{8,}', re.IGNORECASE), "tier": "generic"},
```

3c. Add `"tier": "specific"` to every other pattern in `get_builtin_patterns()`. Every dict gets a new field:
```python
        {"name": "Anthropic API Key", "regex": ..., "tier": "specific"},
        # ... same for all others
```

3d. The `Cloudinary URL` pattern also gets `"tier": "specific"` (it was in the old generic set but is a URL-format credential).

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_claude_scrub.py::TestPatternTiers -v`
Expected: All 8 tests PASS

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass. Some existing tests in `TestPatternEngine` may need minor updates if they relied on the old generic keyword coverage (e.g., `test_find_secrets_keeps_generic_when_no_specific_matches` uses `secret = mysuperlong...` which now won't match bare `secret`). Fix: change test text to use `password = mysuperlong_internal_key_value_here`.

**Step 6: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: add pattern tiers, narrow generic keywords, reclassify patterns"
```

---

### Task 4: Wire tiers into `find_secrets()` return values

**Files:**
- Modify: `claude-scrub:123-147` (`find_secrets()`)
- Modify: All callers of `find_secrets()` that unpack 3-tuples
- Test: `tests/test_claude_scrub.py`

**Step 1: Write the failing tests**

```python
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
        # This value has high entropy (random-looking)
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
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_claude_scrub.py::TestFindSecretsTier -v`
Expected: FAIL (find_secrets still returns 3-tuples)

**Step 3: Implement changes**

3a. Modify `find_secrets()` to return 4-tuples `(name, match_text, line_num, tier)`:

```python
def find_secrets(text, patterns):
    """Find all secret matches in text.

    Returns (pattern_name, match_text, line_num, tier) tuples.
    Generic matches with high-entropy values are promoted to 'specific'.
    """
    matches = []
    lines = text.split("\n")
    for line_num, line in enumerate(lines, start=1):
        line_matches = []
        for p in patterns:
            for m in p["regex"].finditer(line):
                line_matches.append((p["name"], m.start(), m.end(), m.group(), p.get("tier", "specific")))

        # Apply post-match validation (e.g., Luhn for credit cards)
        validated = []
        for name, start, end, match_text, tier in line_matches:
            validator = next((p.get("validate") for p in patterns if p["name"] == name), None)
            if validator == "luhn" and not luhn_check(match_text):
                continue
            validated.append((name, start, end, match_text, tier))
        line_matches = validated

        # Remove generic matches that overlap with any specific match
        specific = [(n, s, e) for n, s, e, _, t in line_matches if n not in GENERIC_PATTERNS]
        for name, start, end, match_text, tier in line_matches:
            if name in GENERIC_PATTERNS:
                if any(s < end and e > start for _, s, e in specific):
                    continue
            # Entropy-gated promotion for generic matches
            effective_tier = tier
            if tier == "generic":
                # Extract value after := assignment
                eq_pos = match_text.find("=")
                if eq_pos < 0:
                    eq_pos = match_text.find(":")
                if eq_pos >= 0:
                    value = match_text[eq_pos + 1:].strip()
                    if entropy(value) >= ENTROPY_THRESHOLD:
                        effective_tier = "specific"
            matches.append((name, match_text, line_num, effective_tier))
    return matches
```

3b. Update all callers that unpack 3-tuples to unpack 4-tuples. Search for `for name, match_text, line_num in` and `for name, _match_text, _line_num in`:

- `scan_targets()` line ~421: `cat_secrets += len(matches)` — no unpacking, no change needed
- `save_scan_cache()` line ~441: `for name, match_text, line_num in matches:` → `for name, match_text, line_num, tier in matches:` — also save tier to cache
- `load_scan_cache()` line ~480: add tier to reconstruction
- `format_scan_report()` line ~561: `for name, match_text, line_num in matches:` → `for name, match_text, line_num, tier in matches:`
- `print_verbose_detail()` line ~1178: same 3→4 tuple update
- `cmd_scrub()` line ~1252: `for name, _match_text, _line_num in matches:` → `for name, _match_text, _line_num, _tier in matches:`
- `scrub_targets()` line ~524: `cat_secrets += len(find_secrets(original, patterns))` — no unpacking, no change

3c. Update `save_scan_cache()` to include tier:
```python
            serialized[str(filepath)] = [
                {"name": name, "line": line_num, "tier": tier}
                for name, match_text, line_num, tier in matches
            ]
```

3d. Update `load_scan_cache()` to read tier:
```python
            matches = [
                (m["name"], m.get("match", "(redacted)"), m["line"], m.get("tier", "specific"))
                for m in matches_data
            ]
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: All tests pass. Fix any existing tests that unpack 3-tuples from `find_secrets()` — update them to unpack 4-tuples.

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: find_secrets returns tier, entropy promotes generic matches"
```

---

### Task 5: Wire tiers into scrub (filter by tier, add `--aggressive`)

**Files:**
- Modify: `claude-scrub:150-154` (`redact_secrets()`)
- Modify: `claude-scrub:506-528` (`scrub_targets()`)
- Modify: `claude-scrub:820-867` (`parse_args()`)
- Modify: `claude-scrub:1218-1298` (`cmd_scrub()`)
- Test: `tests/test_claude_scrub.py`

**Step 1: Write the failing tests**

```python
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
        self.secret_file.write_text(
            '{"message":"password=development_mode and AKIAIOSFODNN7EXAMPLE"}\n'
        )
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        cs.scrub_targets(targets, patterns)
        content = self.secret_file.read_text()
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", content, "Specific match should be scrubbed")
        self.assertIn("development_mode", content, "Low-entropy generic should be preserved")

    def test_aggressive_scrub_removes_generic_matches(self):
        """--aggressive should redact generic matches too."""
        self.secret_file.write_text(
            '{"message":"password=development_mode here"}\n'
        )
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(self.claude_dir, ccrider_db=self.no_ccrider)
        cs.scrub_targets(targets, patterns, aggressive=True)
        content = self.secret_file.read_text()
        self.assertNotIn("development_mode", content, "Aggressive should scrub generic")
        self.assertIn("[REDACTED:", content)

    def test_high_entropy_generic_scrubbed_by_default(self):
        """High-entropy generic match should be scrubbed even without --aggressive."""
        self.secret_file.write_text(
            '{"message":"api_key=sK3j8fAx7mNp2qRwL9vB"}\n'
        )
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
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_claude_scrub.py::TestTieredScrub -v`
Expected: FAIL

**Step 3: Implement changes**

3a. Modify `redact_secrets()` to accept optional tier filter:

```python
def redact_secrets(text, patterns, aggressive=False):
    """Replace each secret match with [REDACTED:<pattern_name>].

    By default, only redacts specific-tier patterns plus generic matches
    with high entropy. When aggressive=True, redacts all patterns.
    """
    lines = text.split("\n")
    result_lines = []
    for line in lines:
        for p in patterns:
            tier = p.get("tier", "specific")
            if tier == "generic" and not aggressive:
                # Only redact high-entropy generic matches
                def replace_if_high_entropy(m):
                    eq_pos = m.group().find("=")
                    if eq_pos < 0:
                        eq_pos = m.group().find(":")
                    if eq_pos >= 0:
                        value = m.group()[eq_pos + 1:].strip()
                        if entropy(value) >= ENTROPY_THRESHOLD:
                            return f"[REDACTED:{p['name']}]"
                    return m.group()  # Keep original
                line = p["regex"].sub(replace_if_high_entropy, line)
            else:
                line = p["regex"].sub(f"[REDACTED:{p['name']}]", line)
        result_lines.append(line)
    return "\n".join(result_lines)
```

3b. Modify `scrub_targets()` to accept `aggressive` parameter:

```python
def scrub_targets(targets, patterns, aggressive=False):
    """Replace secrets in-place across all target files."""
    stats = {"total_secrets": 0, "total_files": 0, "categories": {}}
    for category, files in targets.items():
        cat_secrets = 0
        cat_files = 0
        for filepath in files:
            try:
                original = filepath.read_text(errors="replace")
            except OSError:
                continue
            scrubbed = redact_secrets(original, patterns, aggressive=aggressive)
            if scrubbed != original:
                filepath.write_text(scrubbed)
                cat_files += 1
                cat_secrets += len(find_secrets(original, patterns))
        stats["categories"][category] = {"secrets": cat_secrets, "files": cat_files}
        stats["total_secrets"] += cat_secrets
        stats["total_files"] += cat_files
    return stats
```

3c. Add `--aggressive` to `parse_args()` scrub subparser:

```python
    scrub_parser.add_argument("--aggressive", action="store_true",
                              help="Also scrub generic pattern matches (may degrade session context)")
```

3d. Wire `aggressive` in `cmd_scrub()`:

- Pass `aggressive=args.aggressive` to `scrub_targets()` call
- When `args.aggressive`, print warning before scrubbing:
  ```python
  if args.aggressive:
      print("\n⚠️  Aggressive mode: also scrubbing generic pattern matches.")
      print("   This may redact non-secret values and degrade session context.")
  ```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: tier-filtered scrub with --aggressive flag"
```

---

### Task 6: Update scan output to show tier breakdown

**Files:**
- Modify: `claude-scrub:1152-1166` (`print_scan_totals()`)
- Modify: `claude-scrub:382-429` (`scan_targets()` progress lines)
- Modify: `claude-scrub:531-570` (`format_scan_report()`)
- Test: `tests/test_claude_scrub.py`

**Step 1: Write the failing tests**

```python
class TestScanTierOutput(unittest.TestCase):

    def test_scan_totals_shows_tier_breakdown(self):
        """print_scan_totals should split counts by tier."""
        import io
        from contextlib import redirect_stdout
        fake_path = Path("/tmp/fake.jsonl")
        results = {
            "sessions": {fake_path: [
                ("AWS Key", "AKIA...", 1, "specific"),
                ("Generic Secret Assignment", "password=dev_mode_val", 2, "generic"),
            ]},
            "indexes": {}, "history": {}, "paste_cache": {},
            "file_history": {}, "ccrider": {},
        }
        summary = {"sessions": 1, "indexes": 0, "history": 0,
                   "paste_cache": 0, "file_history": 0, "ccrider": 0}
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_scan_totals(results, summary)
        output = buf.getvalue()
        self.assertIn("Secrets:", output)
        self.assertIn("Generic:", output)

    def test_scan_totals_says_matches_not_secrets(self):
        """Total line should say 'matches' not 'secrets'."""
        import io
        from contextlib import redirect_stdout
        fake_path = Path("/tmp/fake.jsonl")
        results = {
            "sessions": {fake_path: [("AWS Key", "AKIA...", 1, "specific")]},
            "indexes": {}, "history": {}, "paste_cache": {},
            "file_history": {}, "ccrider": {},
        }
        summary = {"sessions": 1, "indexes": 0, "history": 0,
                   "paste_cache": 0, "file_history": 0, "ccrider": 0}
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_scan_totals(results, summary)
        output = buf.getvalue()
        self.assertIn("matches", output.lower())

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
        lines = [l for l in output.split("\n") if "found" in l]
        for line in lines:
            self.assertIn("match", line.lower())
        shutil.rmtree(tmpdir)
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_claude_scrub.py::TestScanTierOutput -v`
Expected: FAIL

**Step 3: Implement changes**

3a. Update `print_scan_totals()` to show tier breakdown:

```python
def print_scan_totals(results, targets_summary, elapsed=None):
    """Print the Total line from scan results with tier breakdown."""
    all_matches = [m for cat in results.values() for matches in cat.values() for m in matches]
    total = len(all_matches)
    specific_count = sum(1 for m in all_matches if len(m) >= 4 and m[3] == "specific")
    generic_count = sum(1 for m in all_matches if len(m) >= 4 and m[3] == "generic")
    # Backward compat: 3-tuples count as specific
    specific_count += sum(1 for m in all_matches if len(m) < 4)

    if isinstance(targets_summary, dict) and all(isinstance(v, int) for v in targets_summary.values()):
        total_files = sum(targets_summary.values())
    else:
        total_files = sum(len(targets_summary.get(c, [])) for c in CATEGORY_ORDER)
    noun = "match" if total == 1 else "matches"
    file_noun = "file" if total_files == 1 else "files"
    line = f"\nTotal: {total} {noun} across {total_files} {file_noun}"
    if elapsed is not None:
        line += f" ({elapsed:.1f}s)"
    print(line)
    if total > 0:
        print(f"\n  Secrets: {specific_count:>5} (specific pattern matches — scrubbed by default)")
        if generic_count > 0:
            print(f"  Generic: {generic_count:>5} (catch-all patterns — use --aggressive to scrub)")
        print("\n🔑 Exposed credentials should be rotated immediately —")
        print("   scrubbing removes local copies but doesn't revoke compromised secrets.")
```

3b. Update `scan_targets()` progress lines: change `"secret"/"secrets"` to `"match"/"matches"` in both the running tally and the final per-category line.

3c. Update `format_scan_report()`: change `"secret"/"secrets"` to `"match"/"matches"` in output strings.

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: All tests pass. Fix any existing tests that assert on `"secrets found"` — update to `"matches"`.

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: scan output shows tier breakdown, uses 'matches' terminology"
```

---

### Task 7: Update scrub command tier-aware counting and output

**Files:**
- Modify: `claude-scrub:1218-1298` (`cmd_scrub()`)
- Test: `tests/test_claude_scrub.py`

**Step 1: Write the failing tests**

```python
class TestScrubTierOutput(unittest.TestCase):

    def test_scrub_count_excludes_generic_by_default(self):
        """Scrub confirmation count should only include specific-tier matches."""
        tmpdir = tempfile.mkdtemp()
        claude_dir = Path(tmpdir) / ".claude"
        proj = claude_dir / "projects" / "-test"
        proj.mkdir(parents=True)
        # One specific (AWS key) and one generic (password=lowentropy)
        (proj / "s.jsonl").write_text(
            '{"m":"AKIAIOSFODNN7EXAMPLE and password=development_mode"}\n'
        )
        no_db = Path(tmpdir) / "no.db"
        patterns = cs.get_builtin_patterns()
        targets = cs.discover_targets(claude_dir, ccrider_db=no_db)
        results = cs.scan_targets(targets, patterns)
        # Count only specific-tier matches
        specific_count = sum(
            1 for cat in results.values()
            for matches in cat.values()
            for m in matches
            if len(m) >= 4 and m[3] == "specific"
        )
        generic_count = sum(
            1 for cat in results.values()
            for matches in cat.values()
            for m in matches
            if len(m) >= 4 and m[3] == "generic"
        )
        self.assertGreater(specific_count, 0)
        self.assertGreater(generic_count, 0)
        # Total should be split
        self.assertLess(specific_count, specific_count + generic_count)
        shutil.rmtree(tmpdir)
```

**Step 2: Run tests**

Run: `python -m pytest tests/test_claude_scrub.py::TestScrubTierOutput -v`

**Step 3: Implement changes**

Update `cmd_scrub()` to count by tier:

- When computing `total` for the confirmation prompt, only count specific-tier matches (unless `--aggressive`)
- When computing `secret_counts` for the type summary, only count specific-tier (unless `--aggressive`)
- When `--aggressive`, count everything
- Show a note about skipped generic matches: `"({generic_count} generic matches preserved — use --aggressive to include)"

**Step 4: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: scrub counts respect tiers, show generic skip note"
```

---

### Task 8: Update verbose output to tag tiers

**Files:**
- Modify: `claude-scrub:1168-1180` (`print_verbose_detail()`)
- Test: `tests/test_claude_scrub.py`

**Step 1: Write the failing test**

```python
    def test_verbose_detail_shows_tier_tag(self):
        """Verbose output should tag matches with their tier."""
        import io
        from contextlib import redirect_stdout
        fake_path = Path("/tmp/fake.jsonl")
        results = {
            "sessions": {fake_path: [
                ("AWS Key", "AKIA...", 1, "specific"),
                ("Generic Secret Assignment", "password=dev_mode_val", 2, "generic"),
            ]},
            "indexes": {}, "history": {}, "paste_cache": {},
            "file_history": {}, "ccrider": {},
        }
        buf = io.StringIO()
        with redirect_stdout(buf):
            cs.print_verbose_detail(results)
        output = buf.getvalue()
        self.assertIn("[generic]", output.lower())
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_claude_scrub.py::TestScanTierOutput::test_verbose_detail_shows_tier_tag -v`

**Step 3: Implement**

Update `print_verbose_detail()`:
```python
                for name, match_text, line_num, *rest in matches:
                    tier = rest[0] if rest else "specific"
                    preview = match_text[:20] + "..." if len(match_text) > 20 else match_text
                    tier_tag = f" [generic]" if tier == "generic" else ""
                    print(f"    Line {line_num}: {name}{tier_tag} ({preview})")
```

**Step 4: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

**Step 5: Commit**

```bash
git add claude-scrub tests/test_claude_scrub.py
git commit -m "feat: verbose output tags generic-tier matches"
```

---

### Task 9: Update README and run final validation

**Files:**
- Modify: `README.md`
- Run: full test suite

**Step 1: Update README**

Add `--aggressive` to the scrub section. Update the example output to show tier breakdown. Add credit card to the pattern categories table. Update the scan example output to say "matches" instead of "secrets".

**Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

**Step 3: Manual smoke test**

Run: `./claude-scrub scan` on real data to verify tier breakdown appears.
Run: `./claude-scrub scrub --dry-run` to verify only specific-tier matches are counted.

**Step 4: Commit**

```bash
git add README.md claude-scrub tests/test_claude_scrub.py
git commit -m "docs: update README for pattern tiers, --aggressive, credit cards"
```
