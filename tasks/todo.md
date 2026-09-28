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
## Reliability Phase 1B - Tracing Privacy Hardening

- [x] Strengthen free-text secret redaction.
- [x] Add sensitive tool output summarization.
- [x] Add manual trace retention/pruning helper.
- [x] Add privacy-focused tracing tests.
- [x] Run targeted tracing/routing tests.
- [x] Run `make check`.

## Reliability Phase 2 - Cost Monitoring

- [x] Add best-effort model usage and cost monitoring module.
- [x] Add `model_usage` SQLite table.
- [x] Record one estimated usage row per successful `Agent.chat()` request.
- [x] Keep pricing configurable and avoid hardcoding cloud billing assumptions.
- [x] Add cost monitoring tests and update agent tracing test expectations.
- [x] Run targeted cost/tracing/routing tests.
- [x] Run `make check`.
- [x] Add exact provider token extraction from SDK responses.
- [ ] Add a CLI/HUD cost summary view if useful.

## Reliability Phase 2.1 - Exact SDK Usage Extraction

- [x] Add Anthropic usage extraction from `usage.input_tokens` and `usage.output_tokens`.
- [x] Add OpenAI-compatible usage extraction from `usage.prompt_tokens` and `usage.completion_tokens`.
- [x] Add additive `usage_source` migration for existing `model_usage` tables.
- [x] Carry exact SDK usage through `RoutingResult` without changing routing behavior.
- [x] Keep character-estimate fallback when usage is absent, partial, or malformed.
- [x] Preserve missing-price and local Ollama zero-cost behavior.
- [x] Verify one cost usage call per successful `Agent.chat()`.
- [x] Run targeted cost/tracing/routing tests and `make check`.

## Reliability Phase 3 - Failed Run Persistence And Rerun

- [x] Extend `agent_runs` with additive failed-run fields.
- [x] Persist failed chat attempts with sanitized input and error details.
- [x] Record success status for successful chat runs.
- [x] Add recent failed-run listing helper.
- [x] Add failed-run detail helper.
- [x] Add rerun helper that creates a new request id and links `parent_request_id`.
- [x] Ensure reruns go through normal `Agent.chat()` path.
- [x] Add tests for failure persistence, redaction, rerun linking, and persistence failure isolation.
- [x] Run targeted tracing/cost/routing tests and `make check`.

## Reliability Phase 3.1 - Failed Runs CLI Visibility

- [x] Inspect current interface structure and confirm no HTTP API server exists.
- [x] Add a thin failed-runs CLI/operator helper under `jarvis/tools/`.
- [x] Add list recent failed runs command/helper.
- [x] Add inspect failed run command/helper.
- [x] Add rerun failed run command/helper.
- [x] Keep output sanitized and preview-oriented.
- [x] Add tests for list, inspect, rerun, missing id, no failed runs, and redaction.
- [x] Run CLI smoke test and `make check`.

## Privacy And Responsible-AI Hardening (2026-09-28)

- [x] Per-action user confirmation for email send/reply, iMessage, FaceTime, empty Trash, calendar delete/invites, file delete/move/overwrite (`jarvis/core/confirmation.py`, `tool_safety.requires_confirmation`, `registry.dispatch(confirmed=...)`, `Agent.chat`).
- [x] Prompt no longer contradicts confirmation; confirm prompt appended after router question-stripping.
- [x] Fence untrusted tool output (`<untrusted_tool_output>`) and redact secrets before any model tier sees it; sanitize prior-tier context.
- [x] Redact secrets in conversation memory (SQLite + Chroma) and add `memory.retention_days` (default 90) with FTS delete trigger.
- [x] Auto-prune traces at startup via `tracing.retention_days` (default 30).
- [x] Harden shell denylist; gate browser clicks behind `JARVIS_ALLOW_BROWSER_INTERACTION`.
- [x] Strip secrets from shell/code subprocess env; run code_exec with `python3 -I` in temp dir.
- [x] Vision-keyword screenshots respect `JARVIS_ALLOW_SCREEN_CAPTURE`; stale capture removed.
- [x] AppleScript escaping handles backslashes.
- [x] Tests: `tests/test_privacy_guardrails.py` (83 tests); `make check` 152 passed.
- [ ] Narrow Google OAuth scopes (needs user decision + re-auth via `setup_google.py`).
- [ ] Optional local-only mode: keep sensitive tool output off Tier 2/3 cloud providers.
- [ ] Redact `learning.corrections` and validator failure-log rows; one-time redaction pass over pre-existing memory rows.

## DPIA And Log Privacy (2026-09-28)

- [x] Logs: redaction filter, conversation content as length placeholders (`logging.conversation_content`), shared daily-rotating handler, `logging.retention_days` (14), 0600/0700 perms.
- [x] Delete temp voice/wake-word audio after transcription.
- [x] Redact + retain `routing_metrics`, `validation_failures`, `corrections`, `tool_failures`, `routing_memory`.
- [x] `docs/privacy/DPIA.md` and `docs/privacy/data_inventory.md`.
- [x] DPIA review step in `.claude/skills/pre-push-checklist.md`.
- [ ] DPIA actions A1–A8 (local-only mode, forget/export, HUD indicators, OAuth scopes, shell/code confirm, provider terms, temp screenshot deletion, old-row purge).
