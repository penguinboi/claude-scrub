# claude-scrub Design

A CLI tool to scan and scrub secrets from Claude Code's local session data.

## Problem

Claude Code stores conversation history, clipboard pastes, and file snapshots locally in `~/.claude/`. Users who paste API keys, tokens, or credentials during sessions leave secrets in plaintext across multiple file types. No existing tool addresses this — ccrider, ccresume, and cc-conversation-search all read session data but none scrub it.

## Tool Identity

- **Name**: `claude-scrub`
- **Language**: Python 3.6+ (stdlib only, zero dependencies)
- **Install**: Single executable file, `chmod +x`, add to `PATH`
- **License**: MIT

## Commands

### `claude-scrub scan`

Read-only audit of all Claude Code data files. Reports secret counts without modifying anything.

**Default output** (summary):
```
Scanning Claude Code data...

Sessions:     142 files scanned, 7 secrets found
Index files:    3 files scanned, 0 secrets found
History:        1 file  scanned, 12 secrets found
Paste cache:   45 files scanned, 3 secrets found
File history:  89 files scanned, 1 secret found

Total: 23 secrets found across 280 files
```

**`--verbose` output** adds per-file detail:
```
Sessions:     142 files scanned, 7 secrets found
  ~/.claude/projects/-Users-saley-Code-regrade3/abc123.jsonl: 3 secrets
    Line 42: AWS Access Key (AKIA...)
    Line 189: Stripe Secret Key (sk_live_...)
    Line 201: Generic API Key
  ~/.claude/projects/-Users-saley-Code-myapp/def456.jsonl: 4 secrets
    ...
```

**Flags**:
- `--verbose` / `-v`: Show per-file, per-line detail with pattern names and redacted previews
- `--patterns-db`: Download and use `secrets-patterns-db` (1600+ patterns) instead of built-in set

### `claude-scrub scrub`

Destructive removal of secrets from Claude Code data files. Replaces secret values with `[REDACTED:<pattern-name>]`.

**Behavior**:
1. Runs a full scan first, displays results
2. Prompts for confirmation: `Scrub 23 secrets across 14 files? This cannot be undone. [y/N]`
3. On confirmation, replaces secrets in-place (no `.bak` files — backups would contain plaintext secrets)
4. Reports results after scrubbing

**Flags**:
- `--yes` / `-y`: Skip confirmation prompt
- `--verbose` / `-v`: Show per-file detail
- `--patterns-db`: Use expanded pattern set
- `--include paste-cache,file-history`: Opt-in to scrubbing paste cache and file history (session files and history.jsonl are always included)

### `claude-scrub sessions`

List and resume Claude Code sessions (the original `claude-sessions` functionality).

**Flags**:
- `--latest`: Only show most recent session per project
- `--days N`: Show sessions from last N days (default: 30)
- `--all`: Show all sessions
- `--min-msgs N`: Filter out sessions with fewer than N messages
- `-o FILE`: Write output to file
- `--print`: Output to stdout without pager

## Scan/Scrub Targets

| Target | Path | Scan | Scrub |
|--------|------|------|-------|
| Session files | `~/.claude/projects/*/*.jsonl` | Always | Always |
| Session indexes | `~/.claude/projects/*/sessions-index.json` | Always | Always |
| Prompt history | `~/.claude/history.jsonl` | Always | Always |
| Paste cache | `~/.claude/paste-cache/*` | Always | Opt-in (`--include paste-cache`) |
| File history | `~/.claude/file-history/*` | Always | Opt-in (`--include file-history`) |
| ccrider DB | `~/.config/ccrider/sessions.db` | Always (if exists) | Opt-in (`--include ccrider`) |

Scan always covers everything so users see the full picture. Scrub is opt-in for paste-cache, file-history, and ccrider because those are managed by other tools.

## Secret Patterns

### Built-in Patterns (~40)

Ship with curated high-confidence patterns covering:
- **AI providers**: Anthropic (`sk-ant-`), OpenAI (`sk-`)
- **Cloud**: AWS access keys (`AKIA`), GCP service accounts, Azure connection strings
- **Payment**: Stripe (`sk_live_`, `rk_live_`), Square, PayPal/Braintree
- **Communication**: Slack (`xoxb-`, `xoxp-`), Discord, Twilio, SendGrid, Mailchimp, Mailgun
- **Dev platforms**: GitHub (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`), GitLab (`glpat-`, `glrt-`), npm, PyPI, Shopify, Heroku, Notion, Postman, Datadog, Vercel
- **Social**: Facebook, Twitch
- **Crypto material**: Private keys (RSA/DSA/EC/PGP), JWT tokens
- **Generic catch-alls**: Bearer tokens, Authorization headers, key/token/secret/password assignments, credentials in URLs

### `--patterns-db` Flag

Downloads `secrets-patterns-db` from github.com/mazen160/secrets-patterns-db (MIT licensed, 1600+ patterns) and caches locally at `~/.config/claude-scrub/patterns-db/`. Provides comprehensive scanning at the cost of more false positives.

### Custom Patterns (config file)

Users can define custom patterns in `~/.config/claude-scrub/config.toml`:

```toml
[[patterns]]
name = "Internal API Key"
regex = "mycompany_[a-zA-Z0-9]{32}"

[[patterns]]
name = "Database URL"
regex = "postgres://[^\\s]+"
```

Custom patterns are loaded alongside built-in patterns (and `--patterns-db` patterns if that flag is used).

## Architecture

```
claude-scrub (single file)
├── CLI argument parsing (argparse)
├── Pattern engine
│   ├── Built-in patterns (compiled regexes)
│   ├── Config file loader (TOML parser, stdlib tomllib or fallback)
│   └── patterns-db downloader/loader
├── Scanner
│   ├── File discovery (glob ~/.claude/**)
│   ├── Per-file secret detection
│   └── Report formatter (summary / verbose)
├── Scrubber
│   ├── In-place replacement engine
│   ├── Confirmation prompt
│   └── Post-scrub report
└── Sessions lister (existing claude-sessions logic)
```

Single Python file. No classes needed — functions organized by section. Pattern engine is shared between scan and scrub commands. The sessions command reuses the existing `list-sessions.py` logic with its built-in secret scrubbing for output.

## Future Considerations (not in v1)

- `--watch` mode for continuous monitoring
- Pre-commit hook integration
- JSON output format for CI/CD pipelines
- Pattern update command (`claude-scrub update-patterns`)
