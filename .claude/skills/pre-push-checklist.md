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

## Privacy / DPIA Check

- If the change adds or alters a tool, model/TTS/STT provider, external API, OAuth scope, stored table/file, retention default, env-flag default, or confirmation rule: update `docs/privacy/data_inventory.md` and the affected sections of `docs/privacy/DPIA.md` (risks, measures, actions) in the same change.
- New persisted text must go through `redact_text`/`sanitize_value` and be covered by a retention window.
- New logging of user or assistant content must use `content_preview()`.

## Drift Check

- `requirements.txt` changed without verification or lock strategy.
- Tool schema changed without registry/executor update.
- Router behavior changed without mocked tests.
- Google scopes changed without explicit reason.
- Prompt changed in a way that weakens confirmation/safety boundaries.
