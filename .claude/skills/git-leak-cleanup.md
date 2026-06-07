# Git Leak Cleanup Skill

Use this for suspected leaked secrets, credentials, API keys, tokens, OAuth files, private config, local databases, logs, or accidentally tracked sensitive files.

## Immediate Rules

- Stop and inspect before committing, pushing, or sharing the repository.
- Do not print real secret values in chat, logs, diffs, or handoff notes.
- Do not rewrite Git history unless the user explicitly approves that exact cleanup action.
- Assume any exposed credential may need rotation or revocation.

## Workflow

1. Identify the sensitive file or path.
   - Use `git status --short`.
   - Use `git diff --name-only` and targeted `git diff -- <path>` only when safe.
   - Avoid dumping full secret-bearing files.
2. Determine whether the secret is only in the working tree, staged, committed, or pushed.
   - Use `git ls-files <path>`.
   - Use `git log -- <path>` if commits exist.
   - Use `git status --short` to distinguish staged vs unstaged.
3. Contain the leak.
   - Move real secret values into `.env` or another ignored local file when appropriate.
   - Replace committed/config examples with blanks or placeholders.
   - Update `.gitignore` for local secrets, tokens, DBs, logs, caches, screenshots, and generated artifacts.
4. If credentials were exposed, tell the user to rotate or revoke them with the provider.
5. Remove from the index without deleting local runtime files when appropriate.
   - Prefer `git rm --cached <path>` for tracked local-only files.
   - Never use destructive cleanup or history rewriting without explicit approval.
6. Verify.
   - `git status --short`
   - `git diff --cached --name-only`
   - `git ls-files <sensitive-path>`
   - Secret scanning if already available; ask before installing scanners.
7. Update `HANDOFF.md` with paths and actions, but never include actual secret values.

## Sensitive JARVIS Paths

- `.env`
- `config.yaml`
- `data/google_credentials.json`
- `data/google_token.json`
- `data/jarvis.db`
- `data/chroma/`
- `logs/`
- screenshots, audio captures, and generated runtime artifacts
