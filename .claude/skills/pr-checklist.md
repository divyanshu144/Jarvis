# PR Checklist Skill

Use this before declaring implementation work ready.

## Checklist

- Scope is limited to requested behavior.
- No unrelated application code or generated files changed.
- Tool schemas and registry entries are synchronized.
- High-risk tool changes have explicit safety reasoning.
- Secrets and sensitive local files were not printed or modified.
- Focused tests were added or updated where behavior changed.
- Verification commands were run and recorded in `HANDOFF.md`.
- README or harness docs were updated if commands, architecture, or workflow changed.
- `tasks/todo.md` reflects what remains.
- `tasks/lessons.md` includes durable discoveries.

## Common Verification

```bash
python3 -m pytest tests/test_routing.py -v
git status --short
```

Full app verification requires macOS GUI/audio permissions and configured API keys, so do not claim it unless actually run.
