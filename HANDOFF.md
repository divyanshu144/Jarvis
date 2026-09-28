# Handoff

## Branch

- Current branch: `master`.
- Git state summary: repository has many staged-added files, including app code, generated caches, logs, local data, and Google OAuth artifacts. Do not revert unrelated changes.

## Current Objective

- Implement FDE readiness tracking and weekly analysis support for JARVIS.

## In-Flight Files

- `.gitignore`
- `HANDOFF.md`
- `README.md`
- `config.yaml`
- `jarvis/core/config.py`
- `jarvis/core/fde_analyser.py`
- `jarvis/core/fde_tracker.py`
- `jarvis/core/proactive.py`
- `jarvis/core/tool_safety.py`
- `jarvis/tools/registry.py`
- `tests/test_routing.py`
- `tasks/todo.md`
- `tasks/lessons.md`

## Completed

- Created `jarvis/core/fde_analyser.py` with `FDEAnalyser`.
- Added dry-run weekly analysis payload generation using resume PDF text, current `fde_gaps.json`, project CLAUDE/git summaries, and git activity since last Sunday.
- Set `projects_root` in `config.yaml` to `/Users/divyanshu/Desktop/all projects` and wired `cfg.projects_root` into FDE analyser/tracker defaults.
- Added `project_aliases` in `config.yaml` and made FDE project summaries use alias display names while preserving `directory_name`.
- Updated FDE project summaries to skip directories without a `.git` directory.
- Added focused `generate_build_plan(gap_id, dry_run=True)` support for one FDE gap.
- Added non-dry Claude Sonnet path using the existing Anthropic config/client pattern, with JSON parsing and persistence into `fde_build_plans` and `fde_progress`.
- Wired `jarvis/core/proactive.py` to run weekly FDE analysis once each Sunday at 08:00 during the proactive monitor loop.
- Added root `.gitignore` for Python caches, venvs, local secrets/runtime state, logs, generated analysis output, and local Claude settings.
- Removed sensitive/generated files from the Git index with `git rm --cached -rf` while preserving local files.
- Added `jarvis/core/tool_safety.py` and wired it into `jarvis/tools/registry.py`.
- Added dispatch-level safety gates for shell execution, Python execution, file mutation/sensitive paths, Gmail mutations, Google Calendar mutations, screenshots/screen vision, local/private browser URLs, and risky system actions.
- Updated `README.md` to reflect current routing, expanded tool inventory, architecture, and safety gates.
- Expanded `tests/test_routing.py` with tool safety coverage and dispatch blocked/allowed behavior.
- Reviewed current harness state and repo status.
- Reviewed `README.md`, `jarvis.py`, `jarvis/core/agent.py`, `jarvis/core/router.py`, `jarvis/tools/registry.py`, memory/config/proactive/briefing modules, HUD, voice, TTS, and routing tests.
- Confirmed README is behind the actual code: current code includes more tools and systems than the README lists.
- Read `README.md`, `requirements.txt`, `tests/test_routing.py`, `jarvis.py`, and relevant project structure.
- Inferred stack: Python/macOS desktop assistant with PyQt6 HUD, voice/Whisper, model routing, local tools, Google APIs, SQLite/Chroma memory.
- Created project-level operating docs and reusable workflow skills.
- Created future spec/plan folders under `docs/superpowers/`.
- Read `CLAUDE.md`, `RESOLVER.md`, `tasks/lessons.md`, and `.claude/settings.local.json` before edits.
- Added `.claude/hooks/stop.sh` and registered it under `hooks.Stop`.
- Added `.claude/hooks/pre-tool-use.sh` and registered it under `hooks.PreToolUse` with matcher `Bash`.
- Added `.claude/commands/promote-lesson.md`.
- Updated `tasks/lessons.md` with smoke-test notes for each new workflow component.

## Verification

- Run: `python3 -m py_compile jarvis/core/fde_analyser.py jarvis/core/proactive.py`.
- Result: passed.
- Run: `python3 jarvis/core/fde_analyser.py --dry-run`.
- Result: passed; no API call was made. Payload used `claude-sonnet-4-20250514`, parsed the resume PDF successfully, loaded all 12 FDE gaps, and reported `/Users/divyanshu/projects not found` with empty weekly git activity.
- Run: `python3 jarvis/core/fde_analyser.py --dry-run` after setting `projects_root`.
- Result: passed; no API call was made. Projects section now includes `FDE-Learning`, `Job_Ready_Agent`, `My_Portfolio`, `docchat`, and `promptOps_framework`.
- Run: dry-run context extraction after project filtering and aliasing.
- Result: passed; projects now include `JobFit Agent`, `Portfolio`, `DocChat Agent`, and `PromptOps`. `FDE-Learning` is excluded because it is not a git repository.
- Run: `python3 -m py_compile jarvis/core/tool_safety.py jarvis/tools/registry.py tests/test_routing.py`.
- Result: passed.
- Run: `python3 -m pytest tests/test_routing.py -v`.
- Result: sandboxed run failed during pytest plugin setup because `pytest_rerunfailures` attempted to bind a local socket; reran with approved escalation and `26 passed in 0.83s`.
- Run: `git ls-files config.yaml data logs graphify-out '**/__pycache__'`.
- Result: no output; sensitive/generated paths are no longer tracked in the index.
- Run: `git status --short --ignored config.yaml data logs graphify-out jarvis/core/__pycache__ tests/__pycache__`.
- Result: paths show as ignored.
- Run: read-only code inspection with `git status --short`, `rg --files`, and targeted `sed` reads.
- Result: review completed; no application code changed.
- Run: `find CLAUDE.md RESOLVER.md HANDOFF.md HANDOFF.template.md tasks .claude/skills docs/superpowers -maxdepth 4 -type f -print`.
- Result: confirmed all requested harness files and placeholder folder files exist.
- Run: `python3 -m pytest tests/test_routing.py -v`.
- Result: first sandboxed run failed during pytest plugin setup because `pytest_rerunfailures` attempted to bind a local socket. Reran with approved escalation; `18 passed in 0.96s`.
- Run: `.claude/hooks/stop.sh`.
- Result: passed silently while `HANDOFF.md` was fresh.
- Run: `python3 -m json.tool .claude/settings.local.json`.
- Result: settings JSON is valid after hook registration.
- Run: synthetic PreToolUse payload for `echo ok` under `/Users/divyanshu/desktop/FDE_Projects/docchat-alpha`.
- Result: passed silently.
- Run: synthetic PreToolUse payloads for `rm -rf build` and `psql prod -c "DELETE FROM users"` under `/Users/divyanshu/desktop/FDE_Projects/docchat-alpha`.
- Result: both blocked loudly with the exact command.
- Run: synthetic PreToolUse payload for `rm -rf build` under `/Users/divyanshu/Desktop/Jarvis`.
- Result: passed silently because the requested hook scope is docchat worktrees.
- Run: `rg -n "Always stop for human approval|Pattern:|3 or more|RESOLVER" .claude/commands/promote-lesson.md` and a small pattern-count script over `tasks/lessons.md`.
- Result: command includes the approval gate; no current pattern has 3 or more occurrences.
- Not run: full app startup, because it requires API keys, macOS permissions, audio/HUD environment, and may trigger external/system actions.

## Open Questions

- Credentials were previously staged locally. Decide whether to rotate Google/API credentials before any remote push or sharing.
- None for FDE project root; configured root is now `/Users/divyanshu/Desktop/all projects`.

## Risks

- Weekly analysis will call Anthropic on Sundays at 08:00 when the proactive monitor is running and `ANTHROPIC_API_KEY` or `config.yaml` has a valid key.
- `FDE-Learning` exists under the project root but is not a git repository and has no `CLAUDE.md`; it is intentionally skipped in analyser context.
- Safety gates are dispatch-level and environment-variable controlled. They reduce accidental/model-triggered execution, but direct imports of executor modules can still bypass the registry by design for tests/internal use.
- Full app startup was not run because it needs API keys, GUI/audio permissions, and can trigger external/system actions.

## Next Action

- Continue with live FDE analysis only when an Anthropic key is available and the Sunday 08:00 proactive run is desired.
## Latest FDE Project Root Note

- Confirmed /Users/divyanshu/Desktop/All Projects/Jarvis exists with .git and CLAUDE.md.
- Updated config.yaml to use /Users/divyanshu/Desktop/All Projects and alias Jarvis to JARVIS.
- Dry-run project list now includes JARVIS, JobFit Agent, Portfolio, DocChat Agent, and PromptOps.
## Latest FDE Tool Note

- Added `jarvis/tools/fde_tool.py` with `fde_tracker` actions: `get_status`, `get_build_plan`, `mark_done`, `what_to_work_on`, and `weekly_summary`.
- Registered `fde_tracker` in `jarvis/tools/registry.py` and added FDE usage guidance to `jarvis/core/agent.py`.
- Added `pypdf>=6.0.0` to requirements because FDE analyser parses the resume PDF with pypdf.
- Verification: `python3 -m py_compile jarvis/tools/fde_tool.py jarvis/tools/registry.py jarvis/core/agent.py` passed.
- Verification: registry validation returned `True` for `fde_tracker` and valid schemas for `get_status` and `mark_done`.
- Verification: `python3 jarvis/tools/fde_tool.py` ran all actions. Claude build-plan generation reached Anthropic but returned 401 invalid x-api-key, so the tool stored and returned a labeled local fallback plan.
## Latest Env Key Loading Note

- Added local `.env` loading to `jarvis/core/config.py`; it populates `os.environ` without overriding shell-provided values.
- Moved API key values out of `config.yaml`; `api_keys` entries are now blank fallbacks.
- Added `.env.example` and ensured `.env` remains ignored.
- `fde_analyser.py` still uses the same central `cfg.anthropic_key` pattern as router/screen vision.
- Verification: `python3 jarvis/tools/fde_tool.py` now returns a Claude-generated MCP build plan instead of the local fallback.
## Latest FDE HUD Panel Note

- Added an FDE Readiness panel to `jarvis/hud/overlay.py` with score, progress bar, delta/review text, scrollable gap list, weekly focus, Build Plan, and Ask JARVIS controls.
- The current overlay has no Projects panel, so the FDE panel is placed in a new lower HUD area while preserving the original arc/history/input widget coordinates.
- Build Plan opens a scrollable popup and calls `fde_tracker get_build_plan` for the selected/top gap.
- Ask JARVIS focuses the input and pre-fills `What should I work on for FDE today?`.
- FDE data refreshes on init and every 60 seconds through `FDETracker().get_summary()`.
- Added `pynput>=1.7.7` to requirements because `jarvis.py` imports it at startup.
- Verification: `python3 -m py_compile jarvis/hud/overlay.py` passed.
- Verification: generated HUD screenshot at `/private/tmp/jarvis_fde_hud.png` and copied to `jarvis_fde_hud.png`.
- Verification: started `python3 jarvis.py`; HUD came online and desktop screenshot was captured at `/private/tmp/jarvis_fde_desktop.png`. Startup logged degraded optional dependencies: ElevenLabs, Whisper, PyAudio, ChromaDB, OpenAI, and Google API client.
## Latest Local TTS Note

- Added optional local Kokoro/Piper TTS support in `jarvis/core/tts.py`.
- TTS order is now ElevenLabs, local Kokoro/Piper, then macOS `say`, unless overridden by `JARVIS_TTS_PROVIDER`.
- Added config/env knobs: `tts.provider`, `tts.local_provider`, `tts.piper_command`, `tts.piper_model_path`, `tts.kokoro_command`, plus matching `.env.example` variables.
- Current machine does not have `piper` or `kokoro` binaries installed, so local TTS is ready but not active until one is installed/configured.
- Verification: `python3 -m py_compile jarvis/core/config.py jarvis/core/tts.py` passed.
- Verification: monkeypatch tests confirmed explicit Piper routing and auto fallback to macOS `say` when Kokoro/Piper are unavailable.
## Latest FDE Startup Briefing Note

- Added FDE tracker initialization to `jarvis.py`; failures are logged and do not block startup.
- Added a 60-second daemon refresh loop that calls `FDETracker.scan_projects()` with guarded error handling.
- Added FDE readiness text to the morning briefing after weather/calendar/email. On Sundays, the briefing triggers `FDEAnalyser.run_weekly_analysis()` when no current-week weekly analysis exists; otherwise it uses cached tracker progress.
- Updated `FDETracker.scan_projects()` to skip non-git directories and move matching open gaps to `in_progress` when detection signals appear.
- Added FDE tests for JSON loading, signal detection, score range, dry-run build-plan structure, and voice-gap quiz behavior.
- Verification: `python3 -m py_compile jarvis.py jarvis/core/briefing.py jarvis/core/fde_tracker.py tests/test_routing.py` passed.
- Verification: `python3 -m pytest -v` passed with 31 tests. `pytest` was installed into the current Python environment because it was missing.
## Latest Claude Workflow Hardening Note

- Added repo-safe shared hook config in `.claude/settings.json`; local permissions and MCP choices remain in `.claude/settings.local.json`.
- Updated `.claude/hooks/stop.sh` so read-only clean sessions can stop without a fresh handoff, while dirty sessions still require a fresh `HANDOFF.md`.
- Updated `.claude/hooks/pre-tool-use.sh` to apply to `/Users/divyanshu/Desktop/All Projects/Jarvis` instead of the old docchat worktree scope, preserving hard blocks for `rm -rf`, force push, SQL drop/delete/truncate hazards.
- Added `.claude/skills/conventions.md` for JARVIS-specific placement, config, tool safety, subprocess, AppleScript, provider mocking, and GUI/audio verification rules.
- Added `.claude/skills/git-leak-cleanup.md` for suspected secret/token/credential exposure handling without printing secrets or rewriting history without approval.
- Strengthened `RESOLVER.md` routing for secrets, conventions/config, voice/audio, and tool/schema/registry work.
- Added root `Makefile` with `make check`, `make test`, `make fmt`, `make lint`, and `make run`.
- Updated `CLAUDE.md` with explicit session-start commands, required file reads, and `make check` as the default verification gate.
- Added a reusable `tasks/lessons.md` template and tightened `.claude/commands/promote-lesson.md` so lesson promotion counts exact `Pattern:` lines.

Files changed in this hardening pass:

- `.claude/settings.json`
- `.claude/hooks/stop.sh`
- `.claude/hooks/pre-tool-use.sh`
- `.claude/skills/conventions.md`
- `.claude/skills/git-leak-cleanup.md`
- `.claude/commands/promote-lesson.md`
- `RESOLVER.md`
- `Makefile`

## Latest Resume-Numbers Research Note (2026-09-17)

### Branch
- `master`.

### Current Objective
- Read-only: extract concrete, verifiable numbers (scale, baseline/improvement, cost, reliability, one defensible architecture decision) from the codebase and live `data/jarvis.db` telemetry for the user's resume bullet. No code changes requested or made.

### In-Flight Files
- None. No files were edited as part of this note-taking task. Pre-existing uncommitted changes from prior sessions (`jarvis/core/agent.py`, `jarvis/core/metrics.py`, `jarvis/core/router.py`, `jarvis/core/tracing.py`, `tasks/lessons.md`, `tasks/todo.md`, `tests/test_routing.py`, `tests/test_tracing.py`, plus untracked `docs/JARVIS_architecture_deep_dive.md`, `jarvis/core/costs.py`, `jarvis/tools/failed_runs.py`, `tests/test_costs.py`, `tests/test_failed_runs_cli.py`) are unchanged and untouched by this session.

### Completed
- Ran `python3 -m pytest -q`: 69 passed in 0.97s (repo currently green).
- Queried `data/jarvis.db` directly (`routing_metrics`, `validation_failures`, `tool_runs`, `conversations`, etc.) for real (non-mocked) usage numbers: 116 logged routing decisions, Tier 1/2/3 split 83/28/5 (71.6%/24.1%/4.3%), avg wall-time by tier 9,626ms / 15,016ms / 35,261ms.
- Confirmed `jarvis/data/model_costs.json` does not exist in the repo, so `costs.py` pricing currently resolves to `missing_price` / $0.00 for non-local providers — flagged to the user as not a real cost-savings figure to cite.
- Read `docs/JARVIS_architecture_deep_dive.md` (existing untracked interview-prep doc) and cross-verified its claims (tool counts, learning thresholds, test counts) against source.
- Reported all findings to the user in chat with exact file/line citations; no artifact or file was created.

### Verification
- Run: `python3 -m pytest -q`.
- Result: `69 passed in 0.97s`.
- Run: `python3 -c "from jarvis.tools.registry import TOOL_DEFINITIONS; print(len(TOOL_DEFINITIONS))"`.
- Result: `19` (README's tool table at `README.md:63-80` documents only 18, missing `fde_tracker`).
- Run: `sqlite3 data/jarvis.db` queries against `routing_metrics`, `validation_failures`, `tool_runs`.
- Result: confirmed real (not mocked) usage rows exist; numbers reported to user, with a caveat that the 3 `tool_runs` rows look like smoke-test artifacts rather than organic traffic.

### Open Questions
- Same as prior entries: credential rotation decision still pending.
- Whether the user wants `jarvis/data/model_costs.json` populated with real per-model pricing so `costs.py` can report actual (non-zero) spend — currently unresolved.

### Risks
- None introduced this session (no writes to application code or config).
- Carried forward: safety gates remain dispatch-level and bypassable via direct executor import (`docs/JARVIS_architecture_deep_dive.md:278`); credential rotation still outstanding.

### Next Action
- If the user wants defensible cost-in-dollars numbers for the resume (not just token-based cost-avoidance), populate `jarvis/data/model_costs.json` with real provider pricing so `get_cost_summary()` stops returning `missing_price`.
- `CLAUDE.md`
- `tasks/todo.md`
- `tasks/lessons.md`
- `HANDOFF.md`

Verification:

- `git status --short`: repo is dirty from the existing staged/untracked project work.
- `git log -1 --oneline`: failed because current branch `master` has no commits yet.
- `python3 -m json.tool .claude/settings.json`: passed.
- `bash -n .claude/hooks/stop.sh`: passed.
- `bash -n .claude/hooks/pre-tool-use.sh`: passed.
- `make check`: passed; compileall, py_compile, and pytest completed with `31 passed in 1.05s`.

Hook smoke tests:

- Stop hook clean tree: passed, allowed stop.
- Stop hook dirty tree + fresh `HANDOFF.md`: passed, allowed stop.
- Stop hook dirty tree + missing `HANDOFF.md`: passed, blocked with schema guidance.
- Stop hook dirty tree + stale `HANDOFF.md`: passed, blocked with schema guidance.
- PreToolUse hook: passed for blocking `rm -rf`, `git push --force`, `DROP TABLE`, `DROP DATABASE`, `DELETE FROM` without `WHERE`, and prod `TRUNCATE`; safe `echo ok` was silent; old docchat path is no longer scoped.

Limitations / Follow-up:

- The Makefile `fmt` and `lint` targets are initial verification gates, not real formatting or static linting. Add Ruff later only if explicitly requested.
- The repository still has a large dirty worktree from prior project setup and feature work; no commit or push was made.
## Latest Commit Preparation Note

- User requested committing and pushing the recent work.
- Pre-commit verification ran `make check`; result: passed with `31 passed`.
- Sensitive path check found no staged `config.yaml`, `.env`, `.claude/settings.local.json`, `data/`, `logs/`, generated screenshots, pycache, or graph/cache artifacts.
- Redacted staged-content scan flagged only placeholder env variable names and code-level API key/token variable references; no real secret values were printed or identified.
- `git remote -v` returned no configured remotes, so push will require adding/providing a remote after the commit.
## Latest Commit Result

- Created initial commit for recent JARVIS workflow and FDE tracker work.
- Commit before handoff amend: `5055863 Initial JARVIS assistant workflow and FDE tracker`.
- Push attempt command: `git push`.
- Push result: failed because no push destination/remote is configured. Configure a remote with `git remote add <name> <url>` and push with `git push <name> master` or set upstream.
## Latest Reliability Phase 1 Observability Note

Objective:

- Implement Phase 1 observability/tracing only. No cost monitoring, evals, hallucination checks, context manager, harness refactor, routing behavior changes, safety policy changes, or tool behavior changes were added.

Architecture summary from exploration:

- JARVIS runtime starts in `jarvis.py`; user text flows through `Agent.chat()`, then `Router.route()`, then memory/metrics persistence and caller-side HUD/TTS.
- Routing lives in `jarvis/core/router.py` with hard routes, learned tier suggestions, Tier 1 Ollama, Tier 2 Groq, and Tier 3 Anthropic/Groq fallback.
- Tools are validated in router tier loops and executed through `jarvis/tools/registry.py::dispatch()`.
- Safety policy lives in `jarvis/core/tool_safety.py` and runs inside `dispatch()` before executor invocation.
- SQLite persistence already exists in memory, metrics, learning, and FDE modules using `cfg.db_path`.
- Tests are pytest-based with mocked provider SDKs and direct tool smoke tests in `tests/test_routing.py`.

Files changed:

- `jarvis/core/tracing.py`
- `jarvis/core/agent.py`
- `jarvis/core/router.py`
- `jarvis/core/metrics.py`
- `jarvis/tools/registry.py`
- `tests/test_tracing.py`
- `tests/test_routing.py`
- `tasks/todo.md`
- `tasks/lessons.md`
- `HANDOFF.md`

Database tables added:

- `agent_runs`: request-level trace row with request id, sanitized user message, route/intent/tier/model metadata, tool/safety JSON fields, final answer/error, latency, and created timestamp.
- `tool_runs`: per-tool trace row with request id, tool name, sanitized tool args JSON, status, result summary/error, latency, and created timestamp.

Wiring completed:

- `Agent.chat()` creates one `request_id`, starts an `agent_runs` row, passes the id to `Router.route()`, and finishes the row on success or error.
- `Router.route()` accepts optional `request_id` and forwards it to tier tool dispatch calls.
- `RoutingResult` now carries optional `chosen_model` and `tools_executed` metadata for tracing while preserving existing positional fields.
- `registry.dispatch()` accepts optional `request_id` and records tool runs/safety blocks only when a request id is present, preserving direct tool call behavior.

Trace safety behavior:

- Tracing is best-effort; helper functions catch SQLite/redaction failures and log debug messages instead of crashing callers.
- Secret-like keys such as API key, secret, token, password, authorization, cookie, and client/refresh/access token fields are redacted.
- Secret-like values and bearer tokens are redacted.
- Long user messages, tool args, tool outputs, and final answers are truncated before storage.

Not wired yet:

- `tools_requested` is initialized but not populated from raw provider tool-call proposals beyond executed tool metadata.
- Tier 3 model metadata is approximate when Anthropic falls back to Groq after an Anthropic exception.
- No HUD or CLI trace viewer exists yet.
- No cost, eval, hallucination, context compression, or harness refactor work was done.

Verification:

- `python3 -m py_compile jarvis/core/tracing.py jarvis/core/agent.py jarvis/core/router.py jarvis/core/metrics.py jarvis/tools/registry.py tests/test_tracing.py tests/test_routing.py`: passed.
- `python3 -m pytest tests/test_tracing.py tests/test_routing.py -v`: passed with 38 tests.
- `make check`: passed; compileall, py_compile, and pytest completed with 38 tests passing.

Risks / follow-up:

- Trace tables can grow over time; add retention or pruning before heavy long-running use.
- Trace rows intentionally store sanitized snippets, not full private data. Do not use them as an audit source for full email/calendar/screen content.
- Next recommended phase is cost monitoring, using this request/tool trace foundation.
## Latest Reliability Phase 1B Privacy Hardening Note

Objective:

- Harden tracing privacy before cost monitoring. No cost fields, evals, hallucination checks, context manager, harness refactor, routing changes, model-selection changes, safety-policy changes, or tool behavior changes were added.

Files changed:

- `jarvis/core/tracing.py`
- `jarvis/tools/registry.py`
- `tests/test_tracing.py`
- `tasks/todo.md`
- `tasks/lessons.md`
- `HANDOFF.md`

Redaction patterns added / strengthened:

- Key/value assignments: `password: ...`, `password=...`, `token: ...`, `token=...`, `api_key: ...`, `api_key=...`, `api key is ...`, `secret: ...`, `secret=...`, `x-api-key: ...`.
- Provider env-style keys: `OPENAI_API_KEY=...`, `ANTHROPIC_API_KEY=...`, `GROQ_API_KEY=...`, plus existing provider key shapes.
- Authorization/bearer forms: `Authorization: Bearer ...`, `Bearer ...`.
- Cookie/session-like pairs such as `sessionid=...`, `csrf_token=...`, `jwt=...`.
- Redacted values are now represented as `[REDACTED]`.

Sensitive tool summary behavior:

- `gmail`, `google_calendar`, `calendar`, `screen_vision`, `screenshot`, `browser_control`, `file_manager`, `clipboard`, `shell_exec`, `code_exec`, `system_control`, and `spotlight` are treated as sensitive trace sources.
- Sensitive tool result summaries now store a privacy summary and output length, not raw tool output content.
- Non-sensitive tool output keeps the existing truncated summary behavior with redaction applied.

Retention / pruning behavior:

- Added manual `prune_traces(days_to_keep=30, max_rows=None, db_path=None)`.
- The helper deletes old rows from `tool_runs` and `agent_runs`, and can cap each table to the newest `max_rows`.
- It is not called automatically and remains best-effort/non-crashing.

Verification:

- `python3 -m py_compile jarvis/core/tracing.py jarvis/tools/registry.py tests/test_tracing.py tests/test_routing.py`: passed.
- `python3 -m pytest tests/test_tracing.py tests/test_routing.py -v`: passed with 43 tests.
- `make check`: passed; compileall, py_compile, and pytest completed with 43 tests passing.

Status:

- Safe to proceed to Phase 2 cost monitoring.
- Remaining trace limitation: Tier 3 request-level `tools_executed` summary is still incomplete, though per-tool `tool_runs` rows are recorded when tools execute with a request id.

## Latest Reliability Phase 2 Cost Monitoring Note

Objective:

- Start Phase 2 cost monitoring only. No evals, hallucination checks, context manager, harness refactor, model routing changes, safety policy changes, or tool behavior changes were added.

Files changed:

- `jarvis/core/costs.py`
- `jarvis/core/agent.py`
- `tests/test_costs.py`
- `tests/test_tracing.py`
- `tasks/todo.md`
- `tasks/lessons.md`
- `HANDOFF.md`

Database tables added:

- `model_usage`: request id, provider, model, input tokens, output tokens, total tokens, estimated USD cost, pricing source, usage source, and created timestamp.

Wiring completed:

- `Agent.chat()` now calls `record_chat_usage()` after a successful router result and before finishing the existing trace row.
- Cost monitoring records one estimated usage row per completed chat using `RoutingResult.tier_used`, `RoutingResult.chosen_model`, the user message, and final answer.
- Cost writes are best-effort and catch their own failures, matching tracing isolation behavior.

Privacy / billing behavior:

- Model/provider/source fields are sanitized through the tracing redaction helper.
- Token counts are character-based estimates for now, not provider billing truth.
- Local Ollama usage is treated as zero cost.
- Cloud model pricing is configurable through the cost helper's price-file support; missing prices record `estimated_cost_usd=0.0` with `pricing_source=missing_price` rather than guessing current provider prices.

Verification:

- Initial targeted test command failed under sandbox because logging could not write `/Users/divyanshu/Desktop/All Projects/Jarvis/logs/jarvis.log`; reran with filesystem approval.
- `python3 -m pytest tests/test_costs.py tests/test_tracing.py tests/test_routing.py -v`: passed with 51 tests.
- `make check`: passed; compileall, py_compile, and pytest completed with 51 tests passing.

Limitations / Follow-up:

- Cost rows are request-level estimates only; exact provider token usage extraction from OpenAI-compatible and Anthropic SDK responses is still pending.
- No CLI/HUD cost summary view exists yet, though `get_cost_summary(days=7)` is available for future display/tooling.
- The configured sandbox writable root still points to `/Users/divyanshu/Desktop/Jarvis`, which does not exist; this session required filesystem approval for writes to the actual repo at `/Users/divyanshu/Desktop/All Projects/Jarvis`.
## Latest Reliability Phase 2.1 Exact SDK Usage Extraction Note

Objective:

- Prefer exact SDK token usage for cost monitoring while preserving Phase 2 behavior: one `model_usage` row per successful `Agent.chat()`, best-effort/non-blocking writes, missing-price cost `0.0`, and local Ollama zero-cost behavior.

Files changed:

- `jarvis/core/costs.py`
- `jarvis/core/metrics.py`
- `jarvis/core/router.py`
- `jarvis/core/agent.py`
- `tests/test_costs.py`
- `tests/test_routing.py`
- `tests/test_tracing.py`
- `tasks/todo.md`
- `tasks/lessons.md`
- `HANDOFF.md`

Database/schema update:

- Added additive `usage_source TEXT NOT NULL DEFAULT 'estimated_chars'` migration to `model_usage`.
- Existing databases are migrated by `_ensure_schema()` using `PRAGMA table_info(model_usage)` and `ALTER TABLE` only when the column is absent.

Implementation notes:

- Added `UsageTotals` and `extract_sdk_usage()` in `jarvis/core/costs.py`.
- Anthropic-style usage reads `usage.input_tokens` and `usage.output_tokens`.
- OpenAI-compatible usage reads `usage.prompt_tokens` and `usage.completion_tokens`.
- Partial/malformed usage returns `None` and falls back to character estimates.
- Router tier loops accumulate exact usage from SDK responses and attach `input_tokens`, `output_tokens`, and `usage_source` to `RoutingResult`.
- `Agent.chat()` passes those fields into `record_chat_usage()`; it still writes exactly one usage row after a successful route.

Verification:

- `python3 -m py_compile jarvis/core/costs.py jarvis/core/metrics.py jarvis/core/router.py jarvis/core/agent.py tests/test_costs.py tests/test_tracing.py`: passed.
- `python3 -m pytest tests/test_costs.py tests/test_tracing.py tests/test_routing.py -v`: passed with 57 tests.
- `make check`: passed; compileall, py_compile, and pytest completed with 57 tests passing.

Limitations / Follow-up:

- Cost accounting is still one row per successful chat, not one row per individual provider call. Failed lower-tier attempts in a cascade are not separately costed yet.
- Cloud pricing remains configurable and intentionally not guessed from provider pricing pages.
- No CLI/HUD cost summary view exists yet.
## Latest Reliability Phase 3 Failed Run Persistence And Rerun Note

Objective:

- Persist failed agent/chat attempts and expose backend helpers for listing, detail, and rerun support without changing normal routing/tool behavior.

Files changed:

- `jarvis/core/tracing.py`
- `jarvis/core/agent.py`
- `tests/test_tracing.py`
- `tasks/todo.md`
- `tasks/lessons.md`
- `HANDOFF.md`

Schema update:

- Reused `agent_runs` instead of adding a separate table.
- Added additive columns when absent: `status`, `parent_request_id`, and `error_category`.
- Existing databases are migrated by `_ensure_schema()` using `PRAGMA table_info(agent_runs)` and `ALTER TABLE` only when needed.

Implementation notes:

- `start_agent_run()` now records `status='running'` and optional `parent_request_id`.
- `finish_agent_run()` records `status='success'` by default or `status='failed'` when an error is provided.
- Failed runs store sanitized `user_message`, `error`, and `error_category`; secret-like values are redacted through existing tracing sanitization.
- Added `list_failed_agent_runs()` and `get_agent_run_detail()` in `jarvis/core/tracing.py`.
- Added `Agent.list_failed_runs()`, `Agent.get_failed_run_detail()`, and `Agent.rerun_failed_run()`.
- Reruns create a new request id and call normal `Agent.chat(..., parent_request_id=original_id)`, so tracing and cost monitoring stay on the existing path.
- Failure persistence is guarded so a tracing/persistence failure does not mask the original chat error.

Verification:

- `python3 -m pytest tests/test_tracing.py -v`: passed with 16 tests.
- `python3 -m pytest tests/test_tracing.py tests/test_costs.py tests/test_routing.py -v`: passed with 61 tests.
- `make check`: passed; compileall, py_compile, and pytest completed with 61 tests passing.

Limitations / Follow-up:

- There is no HTTP API server in this repo, so backend API support is exposed as `Agent` backend methods for HUD/voice/UI callers rather than FastAPI/Flask endpoints.
- Reruns use the stored redacted user message. This avoids persisting raw secrets but means a rerun of an input containing secrets will use `[REDACTED]` values.
- Failed lower-tier attempts inside an eventual successful cascade are still not individually represented as failed chat runs.
## Latest Reliability Phase 3.1 Failed Runs CLI Visibility Note

Objective:

- Expose failed agent runs and reruns through a simple operator-facing interface without requiring direct Python imports.

Interface decision:

- The repo has no HTTP API server. Existing user/operator surfaces are `jarvis.py`, tool modules, and direct Python entrypoints.
- Added a thin CLI/helper module at `jarvis/tools/failed_runs.py`, runnable with `python3 -m jarvis.tools.failed_runs`.

Files changed:

- `jarvis/tools/failed_runs.py`
- `tests/test_failed_runs_cli.py`
- `tasks/todo.md`
- `tasks/lessons.md`
- `HANDOFF.md`

Commands added:

- `python3 -m jarvis.tools.failed_runs list --limit 20`
- `python3 -m jarvis.tools.failed_runs show <request_id>`
- `python3 -m jarvis.tools.failed_runs rerun <request_id>`

Implementation notes:

- `list_failed_runs()` returns compact summaries with request id, timestamp, status, error category, sanitized message preview, route/tier/model metadata, and parent request id.
- `inspect_failed_run()` returns detailed sanitized fields including error and full stored sanitized message.
- `rerun_failed_run()` creates an Agent through the normal app classes by default and delegates to `Agent.rerun_failed_run()` so tracing and cost monitoring still apply.
- Tests use fake agents for rerun paths to avoid provider/network/model calls.
- CLI output is JSON for easy HUD/script consumption.

Verification:

- `python3 -m py_compile jarvis/tools/failed_runs.py tests/test_failed_runs_cli.py`: passed.
- `python3 -m pytest tests/test_failed_runs_cli.py tests/test_tracing.py -v`: passed with 24 tests.
- `python3 -m jarvis.tools.failed_runs list --limit 1`: passed; local DB currently returned `count: 0` and `No failed runs found.`
- `make check`: passed; compileall, py_compile, and pytest completed with 69 tests passing.

Limitations / Follow-up:

- This is CLI/operator visibility, not a PyQt HUD panel. It is intentionally thin until a concrete HUD interaction is requested.
- Rerun still uses the stored redacted message from `agent_runs`; secrets are not restored.
- The CLI rerun command may initialize normal Agent dependencies because it intentionally routes through `Agent.rerun_failed_run()`.

## Latest Privacy And Responsible-AI Review Note (2026-09-28)

### Branch

- `master`. Working tree already dirty from prior reliability phases (see `git status --short`); this session made no code changes.

### Current Objective

- Answer the user's question: how privacy and responsible-AI criteria are handled in JARVIS and which guardrails exist. Read-only review.

### In-Flight Files

- `HANDOFF.md` (this note only).

### Completed

- Reviewed `jarvis/core/tool_safety.py`, `jarvis/tools/registry.py`, `jarvis/core/tracing.py`, `jarvis/core/validator.py`, `jarvis/core/router.py`, `jarvis/core/agent.py`, `jarvis/core/memory.py`, `jarvis/tools/_google_auth.py`, `jarvis/tools/system_control.py`, `jarvis/tools/shell.py`, `jarvis/tools/code_exec.py`, `.gitignore`, and safety/redaction tests.
- Existing guardrails confirmed: pre-execution `check_tool_safety` gate with env-flag opt-in for shell/code/file-mutation/email/calendar/screen/system mutations; hard blocks for dangerous shell patterns, sensitive runtime paths, and local/private URLs; trace redaction + truncation + sensitive-tool output summarization; `.gitignore` coverage for secrets/runtime data; schema validator; `_MAX_TOOL_ITERS = 8`; subprocess timeouts; AppleScript quote escaping.

### Verification

- Read-only inspection plus `git check-ignore -v` confirming `config.yaml`, `data/`, `logs/` are ignored. No tests run (no code changed). `make check` not run for the same reason.

### Open Questions

- Should the user want per-action HUD confirmation instead of per-session env flags?
- Should conversation memory be redacted/expired, and should sensitive tool output be withheld from cloud tiers (Groq/Anthropic)?

### Risks

- `memory.py` `save_turn` stores raw user/assistant text (incl. email/screen content) in SQLite/Chroma with no redaction or retention.
- Full context, including sensitive tool output, is sent to Tier 2/3 cloud providers.
- No prompt-injection handling: fetched web/email/file content is fed back as trusted text.
- Env-flag approvals are session-wide; prompt text and `router._CONFIRM_RE` discourage/strip confirmation questions.
- Shell denylist is bypassable (`shell=True` in `shell.py` and `system_control._shell`); `code_exec` unsandboxed once enabled.
- Broad OAuth scopes (`gmail.modify`, full `calendar`); `clipboard`, `spotlight`, `app_control`, browser clicks ungated.
- `prune_traces` is manual only; no tests for `system_control`/screen/calendar gating.

### Next Action

- If the user approves: (1) redact + add retention to conversation memory, (2) per-action HUD confirmation for email/iMessage/file delete, (3) wrap tool output as untrusted data in prompts, (4) add missing gating tests.

## Latest Privacy And Responsible-AI Hardening Note (2026-09-28)

### Branch

- `master` (uncommitted; builds on prior uncommitted reliability phases).

### Current Objective

- Implement the guardrail fixes from the privacy/responsible-AI review.

### In-Flight Files

- New: `jarvis/core/confirmation.py`, `tests/test_privacy_guardrails.py`.
- Modified: `jarvis/core/tool_safety.py`, `jarvis/tools/registry.py`, `jarvis/core/agent.py`, `jarvis/core/router.py`, `jarvis/core/memory.py`, `jarvis/core/config.py`, `jarvis/core/tracing.py`, `jarvis.py`, `jarvis/tools/shell.py`, `jarvis/tools/code_exec.py`, `jarvis/tools/system_control.py`, `jarvis/tools/apple_music.py`, `tasks/todo.md`, `tasks/lessons.md`.

### Completed

- Per-action confirmation (email send/reply, iMessage, FaceTime, empty Trash, calendar delete/invites, file delete/move/overwrite); user says confirm/cancel; any other message drops it; 120 s TTL.
- Untrusted-output fencing + secret redaction for all tiers; prior-tier context sanitized; prompt rules for untrusted content and confirmations.
- Memory redaction + 90-day retention (`memory.retention_days`, 0 disables); FTS delete trigger; trace pruning at startup (`tracing.retention_days`, default 30).
- Hardened shell denylist; browser click gate; secret-free subprocess env; `python3 -I` for code_exec; screenshot gate on vision keywords; AppleScript backslash escaping.

### Verification

- `make check`: 152 passed. Mutation check: disabling the confirmation gate or router redaction makes the new tests fail.
- Not run: full app (HUD/voice/Gmail/iMessage) — needs GUI, mic, OAuth, macOS permissions.

### Open Questions

- Narrow OAuth scopes (drop `mark_read` → `gmail.send` + `gmail.readonly`; `calendar.events`)? Requires re-auth.
- Want a local-only mode keeping sensitive tool output off Groq/Anthropic?

### Risks

- First startup after this change deletes conversation turns older than 90 days and traces older than 30 days. Set `memory.retention_days: 0` / `tracing.retention_days: 0` in `config.yaml` to keep them.
- Confirmation adds one extra voice turn for sends/deletes; shell_exec/code_exec remain env-gated only (no per-action confirm).
- Existing pre-change memory rows are not retro-redacted; `learning.corrections` and validator failure rows are still raw.
- Shell denylist is best-effort; the env flag remains the real control.

### Next Action

- Manually test in the running app: with `JARVIS_ALLOW_EMAIL_MUTATION=1`, ask to email yourself → hear confirm prompt → say "confirm". Then decide on OAuth scopes and local-only mode.

## Latest DPIA And Log Privacy Note (2026-09-28)

### Branch

- `master` (uncommitted).

### Current Objective

- Produce a DPIA for JARVIS and fix the plaintext-logging gap it surfaced.

### In-Flight Files

- New: `docs/privacy/DPIA.md`, `docs/privacy/data_inventory.md`, `tests/test_logging_privacy.py`.
- Modified: `jarvis/core/logger.py`, `jarvis/core/config.py`, `jarvis.py`, `jarvis/core/voice.py`, `jarvis/wake_word/stub.py`, `jarvis/core/proactive.py`, `jarvis/core/briefing.py`, `jarvis/core/metrics.py`, `jarvis/core/learning.py`, `jarvis/core/validator.py`, `jarvis/core/memory.py`, `tests/test_privacy_guardrails.py`, `.claude/skills/pre-push-checklist.md`, `tasks/todo.md`, `tasks/lessons.md`.

### Completed

- Logs: secret-redaction filter on all handlers; transcripts/replies/briefings logged as `<N chars, content not logged>` unless `logging.conversation_content: true`; single shared `TimedRotatingFileHandler` (midnight, `logging.retention_days` default 14); logs dir 0700, file 0600.
- Temp voice and wake-word WAVs deleted after transcription.
- Metrics, learning, and validator tables redacted on write and pruned with `memory.retention_days`.
- DPIA (screening, description, necessity, 12-risk register, measures, residual risk, action plan A1–A9, sign-off, review triggers) and data inventory.

### Verification

- `make check`: 158 passed. Full app not run (GUI/mic/OAuth/macOS permissions).

### Open Questions

- Owner sign-off on DPIA §8. Decisions on A4 (OAuth scopes) and A8 (purge pre-existing rows/logs).

### Risks

- Existing `logs/jarvis.log` (~600 KB) still contains historic plaintext transcripts; it will rotate at next midnight and be deleted after 14 rotations. Not manually purged.
- Retention defaults delete conversations >90 days, derived rows >90 days, traces >30 days on next startup.

### Next Action

- Owner reviews/signs DPIA; then implement A1 (local-only mode), A2 (forget/export), A3 (HUD indicators).

## Latest Git History Secret Check Note (2026-09-28)

### Branch

- `master` (uncommitted privacy/DPIA work from earlier notes still in the working tree).

### Current Objective

- Confirm whether sensitive paths (`logs/`, `config.yaml`, `data/`) were ever committed.

### In-Flight Files

- `HANDOFF.md` (this note only). No code changes in this step.

### Completed

- `git log --all --oneline -- logs/ config.yaml data/` returned no commits.
- `git rev-list --all --objects` searched for `config.yaml`, `google_token`/`google_credentials`, `jarvis.db`, `chroma`, `*.log`, `.env`: only `.env.example` found (commit `9e9cd49`); all API key values blank, only non-secret TTS defaults.
- `git ls-files`: no sensitive files tracked.

### Verification

- Read-only git inspection above. `make check` last run earlier this session: 158 passed; no code changed since.

### Open Questions

- Unchanged from the DPIA note: owner DPIA sign-off, A4 (OAuth scopes), A8 (purge old logs/DB rows).

### Risks

- No history rewrite or key rotation needed for git exposure. Secrets remain on local disk; protection relies on `.gitignore`, the pre-push sensitive-path check, and FileVault.

### Next Action

- Owner reviews/signs `docs/privacy/DPIA.md`; then implement A1 (local-only mode), A2 (forget/export), A3 (HUD indicators). Commit the privacy work when ready.

## Latest DPIA Actions And Sign-off Note (2026-09-28)

### Branch

- `master` (uncommitted).

### Current Objective

- Implement DPIA actions A1–A8 and record the owner's sign-off.

### In-Flight Files

- New: `jarvis/core/privacy.py`, `jarvis/tools/privacy_cli.py`, `tests/test_dpia_actions.py`.
- Modified: `jarvis/core/config.py`, `jarvis/core/tool_safety.py`, `jarvis/core/router.py`, `jarvis/core/tts.py`, `jarvis/core/confirmation.py`, `jarvis/core/agent.py`, `jarvis/tools/_google_auth.py`, `setup_google.py`, `jarvis/tools/gmail.py`, `jarvis/tools/screenshot.py`, `jarvis/tools/screen_vision.py`, `jarvis/hud/overlay.py`, `jarvis.py`, `docs/privacy/DPIA.md`.

### Completed (code written, NOT yet verified)

- A1 local-only mode (`privacy.local_only` / `JARVIS_LOCAL_ONLY=1`, default off).
- A2 "export my data" / "forget everything" (confirmed) + `python3 -m jarvis.tools.privacy_cli export|forget --yes|redact-existing`.
- A3 HUD privacy strip, capture flash, first-run privacy notice (marker `data/.privacy_notice_v1`), `voice.wake_word: false` switch.
- A4 scopes `gmail.readonly`, `gmail.send`, `calendar.events`; `mark_read` removed; old broad token refused and revoked by `setup_google.py`.
- A5 shell/code per-action confirmation. A7 temp screenshot deletion. A8 `redact_existing_data` implemented.
- DPIA §6–§8 updated; sign-off recorded as owner-approved, effective once verification passes.

### Verification

- **Not run.** The auto-mode safety classifier returned no verdict for every Bash/web call after the edits, so `make check`, the new tests, and the live A8 redaction could not run.

### Open Questions

- None new. A6 (provider terms) still needs web research.

### Risks

- Untested code across router, agent, HUD, OAuth. Possible import cycle: `tool_safety` now imports `config` (config imports only yaml, so expected fine).
- Existing Google token is now refused until `python setup_google.py` is re-run.
- The live DB/logs still hold pre-hardening plaintext until `redact-existing` runs.

### Next Action

1. `make check` and fix any failures.
2. `python3 -m jarvis.tools.privacy_cli redact-existing` (app not running).
3. A6 research into `docs/privacy/processors.md`; update `data_inventory.md`; republish the DPIA artifact.
4. Owner runs `python setup_google.py`.

## Latest End-To-End Verification Note (2026-09-28)

### Branch

- `master` (uncommitted).

### Current Objective

- End-to-end verification of the privacy/DPIA work.

### In-Flight Files

- New: `tests/test_e2e_flows.py`. Modified: `jarvis/core/agent.py` (redact user text before routing and in rolling history), `tests/test_privacy_guardrails.py` (stale expectation), `docs/privacy/DPIA.md` (verification + sign-off effective).

### Completed

- `make check`: 192 passed (after fixing one stale test that expected `shell_exec` to skip confirmation).
- E2E scenarios on the real stack with scripted models: email confirmation round-trip, prompt injection fenced and unable to send, local-only withholding on escalation (and the documented residual when off), shell env-flag + confirmation, secret redaction across memory/traces/metrics/model context, export + forget.
- Found and fixed: user-typed secrets reached model tiers and rolling history.
- HUD strip and capture flash verified with real PyQt6 widgets (offscreen, launcher's Qt plugin path).
- A8 executed on live data: 348 log lines redacted, 0 left, `logs/jarvis.log` now 0600; DB had no secret patterns; row counts and FTS intact. `chromadb` is not installed (semantic memory never active).

### Verification

- As above. Not run: live app with mic/HUD, Google re-auth.

### Open Questions

- None.

### Risks

- Google tools refuse to run until `python setup_google.py` is re-run (by design).
- Repo `pre-tool-use.sh` hook blocks `rm -rf` even in scratch paths; use fresh dirs instead.

### Next Action

1. Owner: `python setup_google.py`, then a live session per the manual checklist.
2. A6 provider-terms research; republish the DPIA artifact.

## Latest HUD Startup Fix Note (2026-09-28)

### Branch

- `master` (uncommitted).

### Current Objective

- Fix HUD not appearing on launch.

### In-Flight Files

- `jarvis.py` (startup speech removed).

### Completed

- Root cause: `speak()` ran synchronously on the Qt thread before `app.exec()`; the new first-run privacy notice made the HUD wait ~40 s to paint. Startup speech (notice + greeting) removed per owner; the notice is shown as HUD text only.
- Startup at 14:48 applied the 90-day retention default and deleted all 130 conversations (2026-05-12 → 06-06). Owner chose to leave them deleted. A copy is in `data/recovery/jarvis-pre-retention-2026-09-28.db` (0600) until the owner removes it.

### Verification

- `make check`: 192 passed. Owner to relaunch with `./run.sh` to confirm the HUD appears immediately.

### Open Questions

- Morning briefing (6–11 am) still speaks at startup — keep or disable?

### Risks

- `data/recovery/` holds an unmanaged copy of the old conversations (outside retention); scratchpad `e2e-*` copies are temporary but also contain them.
- Tests log into the real `logs/jarvis.log` (e.g. "db unavailable" lines at 14:40).

### Next Action

- Owner relaunches; then `python setup_google.py`; then A6.

## Latest Model Outage Fix Note (2026-09-28)

### Branch

- `master` (uncommitted).

### Current Objective

- Fix "error on every request" after relaunch.

### In-Flight Files

- `config.yaml` (only `groq.model`, `claude.model` lines), `jarvis/core/config.py` (defaults), `jarvis/core/router.py` (docstring, graceful all-tiers-failed), `tests/test_e2e_flows.py`.

### Completed

- Root cause: all three tiers failed. Ollama not running; Groq retired `meta-llama/llama-4-scout-17b-16e-instruct` (404); Anthropic no longer serves `claude-sonnet-4-20250514` (404). Final Groq fallback exception reached the HUD as a traceback.
- Models listed with the owner's keys and tool-calling smoke-tested; switched Tier 2 → `openai/gpt-oss-120b`, Tier 3 → `claude-sonnet-5`.
- Router now returns a plain "can't reach any AI model" answer when every tier fails.

### Verification

- `make check`: 193 passed. Live router round trip: Tier 2 (gpt-oss-120b) and Tier 3 (claude-sonnet-5) both answered.

### Open Questions

- Start Ollama (`ollama serve`, `ollama pull qwen2.5:3b`) so Tier 1 works locally? Needed for local-only mode to be useful.

### Risks

- gpt-oss-120b emits U+202F narrow spaces; cosmetic. One observed arithmetic slip in 10 samples.
- `jarvis/core/fde_analyser.py` reads `cfg.claude_model`, so it moved to claude-sonnet-5 too.

### Next Action

- Owner relaunches `./run.sh`; `python setup_google.py`; optionally start Ollama.
