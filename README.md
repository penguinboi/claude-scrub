# claude-scrub

[![Tests](https://github.com/penguinboi/claude-scrub/actions/workflows/test.yml/badge.svg)](https://github.com/penguinboi/claude-scrub/actions/workflows/test.yml)

**Find and remove secrets from your [Claude Code](https://docs.anthropic.com/en/docs/claude-code) local data.**

Claude Code stores conversation history, clipboard pastes, and file snapshots in `~/.claude/`. If you've ever pasted an API key, token, or password during a session, it's sitting in plaintext on disk. `claude-scrub` finds those secrets and scrubs them.

> Single Python file. Zero dependencies. Just download and run.

> ⚠️ **Scrubbing is not enough.** It only removes local copies of secrets from your disk. If a credential was exposed, it should be **rotated immediately** — scrubbing doesn't revoke compromised keys.

---

## Quick start

```bash
# Install
curl -o ~/.local/bin/claude-scrub \
  https://raw.githubusercontent.com/penguinboi/claude-scrub/main/claude-scrub
chmod +x ~/.local/bin/claude-scrub

# See what's exposed
claude-scrub scan

# Remove it
claude-scrub scrub
```

Make sure `~/.local/bin` is in your `PATH`, or put it wherever you like.

Alternatively, clone and symlink:

```bash
git clone https://github.com/penguinboi/claude-scrub.git
ln -s "$(pwd)/claude-scrub/claude-scrub" ~/.local/bin/claude-scrub
```

## Commands

### `scan` — Audit your data

Read-only scan of all Claude Code data files. Nothing is modified.

```bash
claude-scrub scan
```

```
Scanning Claude Code data...

[422/587] Sessions:       422 files scanned, 31204 matches found
[433/587] Index files:     11 files scanned, 0 matches found
[434/587] History:          1 file scanned, 0 matches found
[586/587] Paste cache:    152 files scanned, 91 matches found
[587/587] ccrider DB:       1 file scanned, 1326 matches found

Total: 32621 matches across 587 files (45.2s)

  Secrets:   4609 (specific pattern matches — scrubbed by default)
  Generic:  28012 (catch-all patterns — use --aggressive to scrub)

🔑 Exposed credentials should be rotated immediately —
   scrubbing removes local copies but doesn't revoke compromised secrets.
```

Scan classifies matches into two tiers. **Specific** patterns have distinctive formats (prefixed API keys, private key headers, Luhn-validated credit cards) and are scrubbed by default. **Generic** patterns are broad catch-alls (`password=...`, `api_key=...`) that may match non-secret values — these are shown in scan output but only scrubbed with `--aggressive`. Generic matches with high [Shannon entropy](https://en.wikipedia.org/wiki/Entropy_(information_theory)) (random-looking values likely to be real secrets) are automatically promoted to the specific tier.

Add `--verbose` for per-file, per-line detail with pattern names and tier tags. Use `--patterns-db` to scan with 1600+ patterns from [secrets-patterns-db](https://github.com/mazen160/secrets-patterns-db).

### `scrub` — Remove secrets

Replaces secrets in-place with `[REDACTED:<pattern-name>]`. No backups are created (backups would contain the secrets).

```bash
claude-scrub scrub
```

```
⚠️  Scrubbing rewrites session files in-place.
   Do not scrub while Claude Code is running — it may corrupt active sessions.

Scrub 4609 secrets? This cannot be undone. [y/N] y

Scrubbed 4609 secrets across 177 files.

Secrets scrubbed by type:
  Authorization Header: 1529
  AWS Access Key: 596
  ...

(28012 generic matches preserved — use --aggressive to include)

🔑 Rotate these credentials NOW — scrubbing only removes local copies.
```

By default, only specific-tier matches are scrubbed. Use `--aggressive` to also scrub generic pattern matches (may degrade session context by redacting non-secret values like config keys).

Use `--dry-run` to preview what would be scrubbed without modifying anything. Use `--yes` to skip confirmation. Use `--include paste-cache,file-history,ccrider` to scrub optional targets (see below).

### `stats` — Usage statistics

See how much you've been using Claude Code.

```bash
claude-scrub stats
```

```
📊 Claude Code Stats

  Sessions:      435 across 19 projects
  Messages:      98,828 (you: 40,532 / claude: 58,296)
  First session: 2026-02-05 (30 days ago)
  Data on disk:  2.1 GB
  Most active:   ~/Code/project/scout (123 sessions, 4,793 msgs)
  Biggest file:  curtail-website/181fdce1.jsonl (74 msgs, 107.8 MB)
```

### `sessions` — Browse and resume

Interactive TUI for browsing past Claude Code sessions, grouped by project.

```bash
claude-scrub sessions
```

Use arrow keys to navigate, Enter to resume a session. Also supports non-interactive output:

```bash
claude-scrub sessions --print              # Markdown to stdout
claude-scrub sessions --days 7 --latest    # Last 7 days, latest per project
claude-scrub sessions --all --min-msgs 10  # All sessions, 10+ messages
claude-scrub sessions -o ~/sessions.md     # Save to file
```

## What gets scanned and scrubbed

| Target | Path | Scan | Scrub |
|--------|------|:----:|:-----:|
| Session files | `~/.claude/projects/*/*.jsonl` | ✔ | ✔ |
| Session indexes | `~/.claude/projects/*/sessions-index.json` | ✔ | ✔ |
| Prompt history | `~/.claude/history.jsonl` | ✔ | ✔ |
| Paste cache | `~/.claude/paste-cache/*` | ✔ | `--include paste-cache` |
| File history | `~/.claude/file-history/*` | ✔ | `--include file-history` |
| ccrider DB | `~/.config/ccrider/sessions.db` | ✔ | `--include ccrider` |

Scan always covers everything so you see the full picture. Scrub defaults to session files, indexes, and history. Paste cache, file history, and ccrider are opt-in because they're managed by other tools — scrubbing them directly could cause issues. After scrubbing sessions, you can rebuild the ccrider DB cleanly with `ccrider sync --force`.

## Secret patterns

### Built-in (40+ patterns)

| Category | Tier | Examples |
|----------|------|----------|
| AI providers | Specific | Anthropic (`sk-ant-`), OpenAI (`sk-`) |
| Cloud | Specific | AWS access keys (`AKIA`), GCP, Azure |
| Payment | Specific | Stripe (`sk_live_`), Square, PayPal/Braintree |
| Communication | Specific | Slack (`xoxb-`), Discord, Twilio, SendGrid, Mailchimp, Mailgun |
| Dev platforms | Specific | GitHub (`ghp_`), GitLab (`glpat-`), npm, PyPI, Heroku, Datadog, Vercel |
| Crypto material | Specific | Private keys (RSA/DSA/EC/PGP), JWT tokens |
| Credit cards | Specific | Luhn-validated card numbers (Visa, Mastercard, Amex, etc.) |
| Auth headers | Specific | Bearer tokens, `Authorization:` headers, credentials in URLs |
| Generic catch-all | Generic | `password=`/`api_key=`/`credential=` assignments |

Patterns sourced from [gitleaks](https://github.com/gitleaks/gitleaks) and [secret-regex-list](https://github.com/h33tlit/secret-regex-list).

### Custom patterns

Add your own in `~/.config/claude-scrub/config.toml`:

```toml
[[patterns]]
name = "Internal API Key"
regex = "mycompany_[a-zA-Z0-9]{32}"

[[patterns]]
name = "Database URL"
regex = "postgres://[^\\s\",}]+"
```

### Extended patterns (`--patterns-db`)

Downloads and caches [secrets-patterns-db](https://github.com/mazen160/secrets-patterns-db) (1600+ patterns in gitleaks format). More comprehensive but may produce more false positives.

```bash
claude-scrub scan --patterns-db
```

Cached at `~/.config/claude-scrub/patterns-db/gitleaks.toml`.

## Requirements

- Python 3.8+ (standard library only, no `pip install`)
- Claude Code installed (`~/.claude/` directory)

## Development

```bash
git clone https://github.com/penguinboi/claude-scrub.git
cd claude-scrub
pip install ruff pytest pre-commit
pre-commit install
python3 -m pytest tests/ -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)
