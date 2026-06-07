# JARVIS Task Resolver

Use this router after reading `CLAUDE.md` and `HANDOFF.md`.

| Request Type | Use Skill | Notes |
| --- | --- | --- |
| Plan a feature or architecture change | `.claude/skills/fde-plan.md` | Produce a plan/spec before coding. Store larger plans in `docs/superpowers/plans/`. |
| Bug fix | `.claude/skills/debug-playbook.md` | Reproduce, locate, isolate, fix, verify. |
| Voice, TTS, wake word, audio | `.claude/skills/debug-playbook.md` plus `.claude/skills/api-conventions.md` | Debug runtime dependencies, provider contracts, macOS permissions, and fallback behavior. |
| Code review | `.claude/skills/fde-review.md` | Findings first. Check correctness, safety, maintainability, tests. |
| API/tool schema/provider work | `.claude/skills/api-conventions.md` | Applies to tool schemas, router calls, Google APIs, browser fetching, streaming/provider contracts. |
| Tool, registry, schema, agent tool | `.claude/skills/api-conventions.md` | Keep tool definitions, validation, safety gates, and executors synchronized. |
| Convention, pattern, where should, config | `.claude/skills/conventions.md` | Follow JARVIS placement, config, tool safety, subprocess, AppleScript, and verification invariants. |
| Frontend/HUD work | `.claude/skills/fde-plan.md` plus `.claude/skills/pr-checklist.md` | PyQt6 HUD changes need visual/state verification when feasible. |
| Backend/core routing work | `.claude/skills/api-conventions.md` plus `.claude/skills/debug-playbook.md` | `agent.py`, `router.py`, `registry.py`, `validator.py`, memory, metrics. |
| Security review or hardening | `.claude/skills/fde-review.md` plus `.claude/skills/pre-push-checklist.md` | Focus on model-to-tool trust boundaries and sensitive paths. |
| Secret, credential, API key, token, leak | `.claude/skills/git-leak-cleanup.md` | Stop before commit/push, identify exposure, rotate credentials, clean index/history only with approval. |
| Refactor | `.claude/skills/fde-plan.md` then `.claude/skills/pr-checklist.md` | Preserve behavior and add tests around risky seams. |
| Pre-push or release check | `.claude/skills/pre-push-checklist.md` | Include secrets, generated files, pycache, logs, data DBs. |
| PR readiness | `.claude/skills/pr-checklist.md` | Confirm verification, docs, risk notes, and handoff. |

Default route for ambiguous implementation requests: `fde-plan` for a short plan, then the most specific implementation skill.
