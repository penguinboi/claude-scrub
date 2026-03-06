# claude-sessions

List and resume your [Claude Code](https://docs.anthropic.com/en/docs/claude-code) conversations from the terminal.

Claude Code stores session data locally but doesn't provide an easy way to browse past conversations or get resume commands. This script reads that data and generates a clean summary.

## What it does

- Scans all `~/.claude/projects/` session data (indexes + raw `.jsonl` files)
- Shows date, summary, git branch, message count, and a copy-pasteable `cd + claude --resume` command
- Groups sessions by project directory
- Scrubs 40+ secret patterns (API keys, tokens, credentials) from summaries before display
- Filters noise (empty sessions, interrupted prompts, exit-only sessions)
- Zero dependencies beyond Python 3.6+ standard library

## Install

```bash
# Download the script
curl -o ~/.local/bin/claude-sessions \
  https://raw.githubusercontent.com/penguinboi/claude-sessions-cli/main/claude-sessions
chmod +x ~/.local/bin/claude-sessions
```

Or clone and symlink:

```bash
git clone https://github.com/penguinboi/claude-sessions-cli.git
ln -s "$(pwd)/claude-sessions-cli/claude-sessions" ~/.local/bin/claude-sessions
```

Make sure `~/.local/bin` is in your `PATH`, or put the script wherever you prefer.

## Usage

```bash
# Show sessions from the last 30 days (default)
claude-sessions

# Show only the most recent session per project
claude-sessions --latest

# Last 7 days
claude-sessions --days 7

# All sessions ever
claude-sessions --all

# Filter out short conversations
claude-sessions --min-msgs 10

# Save to a file
claude-sessions --latest -o ~/sessions.md

# Combine flags
claude-sessions --latest --days 14 --min-msgs 5
```

### Example output

```
# Active Claude Sessions

Last 7 days | Generated 2026-03-05 19:11

## ~/Code/my-project

- **2026-03-05** — Fix authentication bug in login flow (`main`) [45 msgs]
  `cd "~/Code/my-project" && claude --resume a1b2c3d4-e5f6-7890-abcd-ef1234567890`

## ~/Code/other-project

- **2026-03-04** — Add dark mode support (`feature/dark-mode`) [120 msgs]
  `cd "~/Code/other-project" && claude --resume f9e8d7c6-b5a4-3210-fedc-ba0987654321`
```

## Secret scrubbing

Summaries are automatically scrubbed for 40+ secret patterns before display, including:

- **AI providers**: Anthropic, OpenAI
- **Cloud**: AWS, GCP, Azure
- **Payment**: Stripe, Square, PayPal/Braintree
- **Communication**: Slack, Discord, Twilio, SendGrid, Mailchimp, Mailgun
- **Dev platforms**: GitHub, GitLab, npm, PyPI, Shopify, Heroku, Notion, Postman, Datadog, Vercel
- **Social**: Facebook, Twitch
- **Crypto**: Private keys (RSA/DSA/EC/PGP), JWT tokens
- **Generic**: Bearer tokens, Authorization headers, key/token/secret/password assignments, credentials in URLs

Patterns sourced from [gitleaks](https://github.com/gitleaks/gitleaks) and [secret-regex-list](https://github.com/h33tlit/secret-regex-list).

> **Note**: This tool only reads local session metadata (timestamps, summaries, session IDs). It does not read or output full conversation contents. However, session summaries and first prompts *may* contain sensitive information that the user typed. The secret scrubbing is a safety net, not a guarantee. Review output before sharing.

## How it works

Claude Code stores session data in `~/.claude/projects/<project-dir>/`:

1. **`sessions-index.json`** — Structured index with summaries, dates, and message counts (not all projects have this)
2. **`<session-id>.jsonl`** — Raw session logs with messages, metadata, and timestamps

The script reads both sources, deduplicates, and merges them into a unified view.

## Requirements

- Python 3.6+
- Claude Code installed (the `~/.claude/` directory must exist)

## License

MIT
