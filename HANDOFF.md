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

