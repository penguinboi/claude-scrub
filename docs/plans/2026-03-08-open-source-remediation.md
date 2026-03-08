# Open-Source Remediation Plan — 2026-03-08

## HIGH

### OS1. Update repo description
- **Type:** GitHub setting
- **Change:** Update to: "Find and remove secrets from Claude Code local session data"
- **Verify:** `gh repo edit --description "..."`

### OS2. Add SECURITY.md
- **Type:** Repository file
- **Change:** Create SECURITY.md with vulnerability reporting instructions (email or GitHub security advisories)
- **Verify:** File exists in repo root

### OS3. Add CONTRIBUTING.md
- **Type:** Repository file
- **Change:** Create CONTRIBUTING.md covering: dev setup (`git clone && python3 -m pytest`), code style (ruff enforced via pre-commit), PR process, testing expectations
- **Verify:** File exists in repo root

## MEDIUM

### OS4. Create first tagged release
- **Type:** Process
- **Change:** Create CHANGELOG.md with current features, tag v0.1.0, create GitHub release
- **Verify:** `gh release list`

### OS5. Add repository topics
- **Type:** GitHub setting
- **Change:** Add topics: claude, claude-code, security, secrets, secret-scanning, cli, python
- **Verify:** `gh repo edit --add-topic ...`

### OS6. Add issue templates
- **Type:** Repository files
- **Change:** Create `.github/ISSUE_TEMPLATE/bug_report.md` and `.github/ISSUE_TEMPLATE/feature_request.md`
- **Verify:** Files exist under `.github/ISSUE_TEMPLATE/`

### OS7. Add dev setup section to README
- **Type:** Documentation
- **Change:** Add "Development" section with clone, test, pre-commit install commands
- **Verify:** README contains dev instructions

## LOW

### OS8. Add PR template
- **Type:** Repository file
- **Change:** Create `.github/PULL_REQUEST_TEMPLATE.md`
- **Verify:** File exists

### OS9. Add CODE_OF_CONDUCT.md
- **Type:** Repository file
- **Change:** Adopt Contributor Covenant or similar
- **Verify:** File exists in repo root

### OS10. Publish to PyPI
- **Type:** Process + config
- **Change:** Add entry point to pyproject.toml, publish with `python -m build && twine upload`
- **Verify:** `pip install claude-scrub` works
