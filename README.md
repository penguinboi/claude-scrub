# claude-scrub

Scan and scrub secrets from [Claude Code](https://docs.anthropic.com/en/docs/claude-code) local session data.

Claude Code stores conversation history, clipboard pastes, and file snapshots locally. If you've ever pasted an API key or credential during a session, it's sitting in plaintext on disk. This tool finds and removes those secrets.

Also includes a session browser for listing and resuming past conversations.

## What it does

- **`scan`** — Read-only audit of all Claude Code data files for secrets
- **`scrub`** — Remove secrets from session data (in-place, no backups)
- **`sessions`** — List past sessions with resume commands and interactive picker
- Scans 40+ secret patterns (API keys, tokens, credentials) across all data files
- Optional integration with [secrets-patterns-db](https://github.com/mazen160/secrets-patterns-db) for 1600+ patterns
- Custom patterns via TOML config
- Zero dependencies beyond Python 3.6+ standard library

## Install

```bash
curl -o ~/.local/bin/claude-scrub \
  https://raw.githubusercontent.com/penguinboi/claude-scrub/main/claude-scrub
chmod +x ~/.local/bin/claude-scrub
```

Or clone and symlink:

```bash
git clone https://github.com/penguinboi/claude-scrub.git
ln -s "$(pwd)/claude-scrub/claude-scrub" ~/.local/bin/claude-scrub
```

Make sure `~/.local/bin` is in your `PATH`.

## Usage

### Scan for secrets

```bash
# Quick summary of secrets across all Claude Code data
claude-scrub scan

# Detailed per-file, per-line report
claude-scrub scan --verbose

# Use 1600+ patterns from secrets-patterns-db
claude-scrub scan --patterns-db
```

### Scrub secrets

```bash
# Interactive: shows scan results, asks for confirmation
claude-scrub scrub

# Non-interactive
claude-scrub scrub --yes

# Also scrub paste cache and file history (opt-in)
claude-scrub scrub --include paste-cache,file-history

# Include ccrider database too
claude-scrub scrub --include paste-cache,file-history,ccrider
```

### Browse sessions

```bash
# Interactive picker (arrow keys, Enter to resume)
claude-scrub sessions

# Markdown output
claude-scrub sessions --print

# Last 7 days, latest per project
claude-scrub sessions --days 7 --latest

# All sessions with 10+ messages
claude-scrub sessions --all --min-msgs 10

# Save to file
claude-scrub sessions -o ~/sessions.md
```

## What gets scanned

| Target | Path | Scan | Scrub |
|--------|------|------|-------|
| Session files | `~/.claude/projects/*/*.jsonl` | Always | Always |
| Session indexes | `~/.claude/projects/*/sessions-index.json` | Always | Always |
| Prompt history | `~/.claude/history.jsonl` | Always | Always |
| Paste cache | `~/.claude/paste-cache/*` | Always | Opt-in |
| File history | `~/.claude/file-history/*` | Always | Opt-in |
| ccrider DB | `~/.config/ccrider/sessions.db` | Always | Opt-in |

Scan always covers everything so you see the full picture. Scrub is opt-in for paste-cache, file-history, and ccrider because those are managed by other tools.

## Built-in secret patterns

40+ patterns covering:

- **AI providers**: Anthropic, OpenAI
- **Cloud**: AWS, GCP, Azure
- **Payment**: Stripe, Square, PayPal/Braintree
- **Communication**: Slack, Discord, Twilio, SendGrid, Mailchimp, Mailgun
- **Dev platforms**: GitHub, GitLab, npm, PyPI, Shopify, Heroku, Notion, Postman, Datadog, Vercel
- **Social**: Facebook, Twitch
- **Crypto**: Private keys (RSA/DSA/EC/PGP), JWT tokens
- **Generic**: Bearer tokens, Authorization headers, key/token/secret/password assignments, credentials in URLs

Patterns sourced from [gitleaks](https://github.com/gitleaks/gitleaks) and [secret-regex-list](https://github.com/h33tlit/secret-regex-list).

## Custom patterns

Add your own patterns in `~/.config/claude-scrub/config.toml`:

```toml
[[patterns]]
name = "Internal API Key"
regex = "mycompany_[a-zA-Z0-9]{32}"

[[patterns]]
name = "Database URL"
regex = "postgres://[^\\s]+"
```

Custom patterns are loaded alongside built-in patterns.

## Extended patterns (--patterns-db)

The `--patterns-db` flag downloads and caches [secrets-patterns-db](https://github.com/mazen160/secrets-patterns-db) (1600+ patterns in gitleaks format). More comprehensive but may produce more false positives.

```bash
claude-scrub scan --patterns-db
```

The database is cached at `~/.config/claude-scrub/patterns-db/gitleaks.toml`.

## Requirements

- Python 3.6+
- Claude Code installed (`~/.claude/` directory must exist)

## License

MIT
