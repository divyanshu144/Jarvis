# Debug Playbook Skill

Use this for bugs, failing tests, regressions, unexpected tool behavior, or runtime errors.

## Workflow

1. Read `HANDOFF.md` and check `git status --short`.
2. Reproduce with the narrowest safe command.
   - Prefer `python3 -m pytest tests/test_routing.py -v` for routing/schema issues.
   - Use mocks for model providers, Google APIs, browser automation, screenshots, and macOS automation.
3. Locate the failing boundary:
   - user input to `Agent.chat`
   - route decision in `Router.route`
   - tool schema validation in `validate_tool_call`
   - dispatch in `jarvis/tools/registry.py`
   - specific tool executor behavior
   - memory/config loading side effects
4. Isolate the smallest fix.
5. Add or update focused tests when behavior changes.
6. Verify with targeted tests and any safe static checks available.
7. Update `HANDOFF.md`, `tasks/todo.md`, and `tasks/lessons.md` if a durable lesson was learned.

## Safety Notes

- Do not reproduce bugs by sending real email, mutating real calendars, deleting files, emptying trash, running arbitrary shell, or changing system state.
- Avoid launching the full app unless the user explicitly wants GUI/audio/runtime testing.
- If debugging a high-risk tool, prefer unit-level tests with `unittest.mock.patch`.
