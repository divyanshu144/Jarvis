# FDE Plan Skill

Use this for feature planning, architecture changes, refactors, or any request where coding should not start immediately.

## Workflow

1. Read `CLAUDE.md`, `HANDOFF.md`, and `RESOLVER.md`.
2. Check `git status --short`.
3. Identify the impacted area:
   - App startup/HUD: `jarvis.py`, `jarvis/hud/`
   - Agent/routing: `jarvis/core/agent.py`, `jarvis/core/router.py`
   - Tools: `jarvis/tools/registry.py`, specific tool modules
   - Memory/config: `jarvis/core/memory.py`, `jarvis/core/config.py`
   - Voice/TTS/wake word: `jarvis/core/voice.py`, `jarvis/core/tts.py`, `jarvis/wake_word/`
4. Inspect relevant code before proposing changes.
5. Produce a concise plan with:
   - objective
   - files likely touched
   - risks, especially tool execution/secrets/OAuth/system actions
   - verification commands
   - rollback or containment notes for risky work
6. For larger work, create a plan under `docs/superpowers/plans/`.
7. Update `tasks/todo.md` with implementation steps if work will continue.

## Output Standard

- Keep plans specific to this project.
- Do not propose new dependencies unless they clearly reduce risk or complexity.
- Call out when app-level verification is impractical because it requires GUI, microphone, API keys, OAuth, or macOS permissions.
