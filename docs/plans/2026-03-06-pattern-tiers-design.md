# Pattern Tiers and Credit Card Detection

## Problem

claude-scrub's "Generic Secret Assignment" pattern (`key=...`, `token=...`, `secret=...`) matches ~28,000 times in a typical scan. The vast majority are false positives — config values, documentation, code discussion — not actual secrets. Scrubbing all of them degrades session history without meaningful security benefit.

## Design

### Two pattern tiers

| Tier | Scrub default | Description |
|------|:---:|-------------|
| **Specific** | Yes | Distinctive formats that rarely false-positive (prefixed keys, private key headers, Luhn-validated credit cards) |
| **Generic** | No | Catch-all patterns that match by keyword + value assignment |

Scan always reports both tiers. Scrub only redacts specific-tier matches by default.

### Pattern reclassification

These patterns move from the current `GENERIC_PATTERNS` set to **specific** tier:
- Bearer Token — a 20+ char string after `Bearer` is almost always a real token
- Authorization Header — `Authorization:` headers contain real credentials
- Password in URL — `://user:pass@host` embeds real credentials

Only **Generic Secret Assignment** remains in the generic tier.

### Narrowing the generic pattern

Current: `(?:key|token|secret|password|credential|passwd|api_key|apikey)`

The keywords `key`, `token`, and `secret` are too broad. `key` alone matches React keys, database primary keys, config keys, and thousands of non-secret assignments.

New: `(?:password|credential|passwd|secret_key|api_key|apikey|secret_token)`

Drops standalone `key`, `token`, `secret`. Keeps compound forms where they indicate actual credentials.

### Entropy-gated promotion

Generic matches aren't all equal. `api_key=development_mode` (entropy ~3.4) is probably not a secret. `api_key=sk3j8f9aKx7mNp2qR5tY` (entropy ~4.2) probably is.

Shannon entropy measures character-level unpredictability:

```
H(s) = -Σ (p_i × log₂(p_i))
```

Where `p_i` is the frequency of each unique character. High entropy (many unique characters, uniformly distributed) indicates random/generated strings. Low entropy (repeated characters, small alphabet) indicates human-readable text.

| Value | Entropy | Likely |
|-------|---------|--------|
| `development_mode` | ~3.4 | Config value |
| `placeholder123` | ~3.5 | Placeholder |
| `aX9mK2pQ7nL4` | ~3.6 | Borderline |
| `sk3j8f9aKx7mNp2qR5` | ~4.2 | API key |

When a generic pattern matches, extract the value portion and compute its entropy. Above a threshold (~3.8 bits), promote it to specific tier (scrubbed by default). Below, it stays generic (scan-only).

Implementation is ~5 lines using only `math.log2` and `collections.Counter` — no new dependencies.

### Credit card detection

Add a credit card pattern to the **specific** tier:

- Regex: `\b[3-6]\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{1,4}\b`
- Post-match validation: Luhn checksum (digits-only, mod-10 algorithm)
- Luhn validation makes false positives very rare, justifying specific-tier placement

Luhn check is ~8 lines of Python, no dependencies.

### Scan output changes

Split the summary by tier:

```
Total: 32621 matches across 587 files (45.2s)

  Secrets:   4609 (specific pattern matches — scrubbed by default)
  Generic:  28012 (catch-all patterns — use --aggressive to scrub)
```

Progress lines say "matches" instead of "secrets" for honesty.

### Scrub behavior

**Default**: only scrubs specific-tier matches (including entropy-promoted generic matches).

**`--aggressive` flag**: also scrubs all generic matches regardless of entropy. Prints a warning: "Aggressive mode scrubs generic pattern matches which may include non-secret values. Session context may be degraded."

### Verbose output

`--verbose` tags each match with its tier. Generic matches that were entropy-promoted show their entropy value.

## What's not changing

- Scan cache format — adds a `tier` field to each cached match, backward-compatible
- `--patterns-db` and custom patterns — external patterns remain specific-tier by default
- `--include` flag for target categories (paste-cache, file-history, ccrider) — orthogonal to pattern tiers
- `--dry-run` — works the same, just respects tier filtering
- Dedup logic — specific matches still suppress overlapping generic matches on the same line

## Testing

- Unit tests for `entropy()` with known strings and expected values
- Unit tests for Luhn validation with valid/invalid card numbers
- Test that generic patterns don't match on narrowed-out keywords (`key=...`, `token=...`)
- Test entropy promotion threshold (high-entropy generic match → specific tier)
- Test `--aggressive` flag scrubs generic matches
- Test scan output format with tier breakdown
- Integration test: scrub with default settings preserves generic matches in file
- Integration test: scrub with `--aggressive` redacts generic matches
