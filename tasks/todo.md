# Active Tasks

## Claude Code Workflow Harness

- [x] Inspect git status and project structure.
- [x] Read README, dependency files, tests, and entrypoint.
- [x] Infer stack and architecture.
- [x] Create project-specific operating docs.
- [x] Create reusable `.claude/skills` workflows.
- [x] Create future spec/plan folders.
- [x] Run safe verification commands.
- [x] Update `HANDOFF.md` with verification results.

## Backlog

- [x] Add dry-run FDE weekly analyser for resume, gap, project, and weekly git context.
- [x] Wire weekly FDE analysis into proactive Sunday 08:00 briefing.
- [x] Add or update `.gitignore` for secrets, data, logs, generated caches, and `__pycache__`.
- [x] Remove staged sensitive/generated files from Git index while preserving local files.
- [x] Add safety gates around high-risk model-invoked tools before broader use.
- [x] Update README to match current routing, tool inventory, and safety behavior.
- [x] Expand tests around tool safety, schema/registry drift, and prompt-injection boundaries.
- [ ] Decide whether credentials need rotation because they were previously staged locally.
## FDE Progress Tracker

- [x] Add `fde_tracker` tool for status, build plans, progress updates, next-focus guidance, and weekly summary.
- [x] Register `fde_tracker` in the shared tool registry.
- [x] Add FDE tracker routing guidance to the agent system prompt.
- [x] Run direct tool smoke test for all actions.
## FDE HUD Panel

- [x] Add FDE Readiness panel to HUD overlay.
- [x] Add progress bar, gap list, weekly focus, Build Plan, and Ask JARVIS controls.
- [x] Wire panel refresh to FDETracker every 60 seconds.
- [x] Start JARVIS and capture HUD screenshot.
## FDE Startup and Briefing Wiring

- [x] Initialize FDETracker during JARVIS startup without blocking app boot.
- [x] Scan projects every 60 seconds in a guarded background loop.
- [x] Add FDE readiness text to the morning briefing after weather/calendar/email.
- [x] Trigger Sunday weekly analysis when no current-week weekly analysis exists.
- [x] Add five FDE tracker tests to `tests/test_routing.py`.
- [x] Run the full pytest suite.
## Claude Workflow Hardening

- [x] Add repo-safe shared `.claude/settings.json`.
- [x] Update Stop hook to block only dirty-tree stale/missing handoffs.
- [x] Scope Bash safety hook to the JARVIS repo.
- [x] Add JARVIS conventions and git leak cleanup skills.
- [x] Strengthen `RESOLVER.md` routing rows.
- [x] Add root `Makefile` with `make check`.
- [x] Update `CLAUDE.md` session lifecycle and definition of done.
- [x] Add reusable lesson template and tighten promote-lesson counting guidance.
- [x] Run `make check` and hook smoke tests.
## Reliability Phase 1 - Observability Tracing

- [x] Explore agent, router, registry, safety, memory, config, logging, and tests before editing.
- [x] Add best-effort SQLite tracing module.
- [x] Add `agent_runs` and `tool_runs` tables.
- [x] Generate one request id per `Agent.chat()` call.
- [x] Pass request id through router and tool dispatch paths.
- [x] Record tool runs and safety blocks without changing tool outputs.
- [x] Redact secret-like fields and truncate long trace values.
- [x] Add tracing tests and preserve routing/tool tests.
- [x] Run `make check`.

