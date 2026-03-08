# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in claude-scrub — especially in secret detection patterns, the scrubbing logic, or the secure delete implementation — please report it responsibly.

**Do not open a public issue for security vulnerabilities.**

Instead, use one of these channels:

1. **GitHub Security Advisories** (preferred): [Report a vulnerability](https://github.com/penguinboi/claude-scrub/security/advisories/new)
2. **Email**: Open a GitHub issue with the title "Security contact request" and we'll arrange a private channel

## What to Include

- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Potential impact

## Scope

This project is a local CLI tool that runs on the user's machine. The most relevant security concerns are:

- **False negatives**: Secret patterns that fail to detect real credentials
- **Data corruption**: Scrub operations that damage files beyond redacting secrets
- **Path traversal**: File operations that could read/write outside `~/.claude/`
- **Symlink attacks**: Following symlinks to unintended targets

## Response

We aim to acknowledge reports within 48 hours and provide a fix or mitigation within 7 days for critical issues.
