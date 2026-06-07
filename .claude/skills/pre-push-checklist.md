# Pre-Push Checklist Skill

Use this before pushing, sharing, or packaging the repository.

## Commands

```bash
git status --short
python3 -m pytest tests/test_routing.py -v
```

If installed, also run security/dependency checks:

```bash
python3 -m bandit -r jarvis setup_google.py jarvis.py
python3 -m pip_audit -r requirements.txt
```

Do not install scanners without user approval.

## Sensitive Path Check

Flag these before any push:

- `config.yaml`
- `data/google_credentials.json`
- `data/google_token.json`
- `data/jarvis.db`
- `data/chroma/`
- `logs/`
- `*.log`
- `__pycache__/`
- `.pytest_cache/`
- `graphify-out/`
- screenshots or audio captures under `/tmp` or project directories

## Drift Check

- `requirements.txt` changed without verification or lock strategy.
- Tool schema changed without registry/executor update.
- Router behavior changed without mocked tests.
- Google scopes changed without explicit reason.
- Prompt changed in a way that weakens confirmation/safety boundaries.
