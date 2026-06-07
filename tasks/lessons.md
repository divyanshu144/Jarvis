# Lessons Learned

- This repository is a Python/macOS desktop assistant, not a JavaScript full-stack app. Future workflow docs should reference PyQt6 HUD, voice, model routing, local tools, Google APIs, and SQLite/Chroma memory rather than web frontend/backend defaults.
- `README.md` is useful but slightly stale: it lists 10 tools and older architecture notes, while the current tree includes additional tools such as Gmail, Google Calendar, Apple Music, proactive monitoring, learning, metrics, and validator modules.
- `validate_tool_call` checks tool names, required fields, types, and enums, but it does not enforce safety policy. Do not treat schema validation as an approval gate.
- Sensitive local files are present in the worktree: Google OAuth credentials/token, SQLite memory DB, logs, and config. Pre-push checks must flag these paths.
- Automated security scanners were not installed during prior inspection (`bandit`, `pip-audit`, `safety` unavailable). If needed, request approval before installing new tools.
- Pattern: handoff-freshness-hook
  Lesson: A Stop hook can enforce session discipline by checking `HANDOFF.md` modification time and failing loudly with the required schema when stale.
  Evidence: `.claude/hooks/stop.sh` smoke test passed silently when `HANDOFF.md` was fresh; `settings.local.json` remained valid JSON.
- Pattern: worktree-bash-safety-hook
  Lesson: PreToolUse hooks should parse Claude JSON defensively, enforce only the intended worktree path, stay silent on success, and include the exact blocked command on failure.
  Evidence: `.claude/hooks/pre-tool-use.sh` allowed `echo ok`, blocked `rm -rf build` and `DELETE FROM users` under `/Users/divyanshu/desktop/FDE_Projects/docchat-*`, and ignored the Jarvis worktree path.
- Pattern: promote-lesson-approval-gate
  Lesson: Lesson promotion should be a draft-first command: count exact `Pattern:` fields, propose skill and resolver mappings, and stop before file writes until a human approves.
  Evidence: `.claude/commands/promote-lesson.md` contains the approval stop rule; current lessons show no pattern with 3 or more occurrences.
- Pattern: dispatch-level-tool-safety
  Lesson: High-risk model tool calls should be gated at the shared dispatch boundary, not in individual model prompts, because every tier eventually reaches `registry.dispatch()`.
  Evidence: `jarvis/core/tool_safety.py` now blocks shell/code/file mutations, email/calendar mutations, screen capture, local/private browser URLs, and risky system actions before executor invocation.
- Pattern: index-clean-hygiene
  Lesson: Use `git rm --cached -rf` to remove already-staged secrets and generated files from the Git index while preserving local runtime files; pair it with root `.gitignore` entries and verify with `git ls-files`.
  Evidence: `config.yaml`, `data/`, `logs/`, `graphify-out/`, and `__pycache__/` are no longer returned by `git ls-files` and appear as ignored in `git status --ignored`.
- Pattern: fde-analysis-project-root
  Lesson: FDE analysis depends on a real projects root for commit evidence; if `~/projects` is missing, the analyser should preserve the gap/resume context and report the missing directory instead of failing.
  Evidence: `python3 jarvis/core/fde_analyser.py --dry-run` returned a valid Claude payload with `projects: [{"note": "/Users/divyanshu/projects not found"}]` and empty weekly git activity.
- Pattern: configurable-projects-root
  Lesson: Project scanning should read the configured `projects_root` instead of hardcoding `~/projects`, because this machine stores project repos under `/Users/divyanshu/Desktop/all projects`.
  Evidence: After adding `projects_root` to `config.yaml` and wiring `cfg.projects_root`, FDE dry-run found `Job_Ready_Agent`, `My_Portfolio`, `docchat`, and `promptOps_framework` with git commits.
- Pattern: project-evidence-normalization
  Lesson: FDE project context should skip non-git folders and send resume-facing alias names while keeping original directory names for traceability.
  Evidence: Dry-run context now excludes non-git `FDE-Learning` and maps `Job_Ready_Agent` to `JobFit Agent`, `docchat` to `DocChat Agent`, `promptOps_framework` to `PromptOps`, and `My_Portfolio` to `Portfolio`.
- Pattern: project-root-casing
  Lesson: Project scanning should use the actual Desktop folder casing (/Users/divyanshu/Desktop/All Projects) and include aliases for exact directory names, because this repo lives under Jarvis, not lowercase jarvis.
  Evidence: Dry-run context now includes JARVIS with directory_name Jarvis, .git, and CLAUDE.md present.
- Pattern: fde-tool-api-fallback
  Lesson: FDE build-plan tooling should attempt Claude generation but return a useful local fallback when Anthropic authentication fails, while making the failure explicit.
  Evidence: `python3 jarvis/tools/fde_tool.py` exercised all actions; `get_build_plan` hit Anthropic 401 invalid x-api-key and returned a labeled local fallback plan.
- Pattern: env-secret-source-of-truth
  Lesson: API clients should continue using the central `cfg.*_key` accessors, while `Config` loads local `.env` before `config.yaml` so secrets stay out of YAML and callers do not reimplement key loading.
  Evidence: `fde_analyser.py` uses `cfg.anthropic_key`, `config.yaml` API key values are blank, `.env` is ignored, and `python3 jarvis/tools/fde_tool.py` returned a Claude-generated MCP plan.
- Pattern: hud-runtime-dependencies
  Lesson: HUD verification needs PyQt6 and the app startup path also imports pynput; keep runtime imports declared in requirements so UI screenshot checks are repeatable.
  Evidence: HUD screenshot generation required installing PyQt6, and full `python3 jarvis.py` startup initially failed until `pynput` was installed and added to requirements.
- Pattern: fde-hud-no-project-panel
  Lesson: The current HUD overlay has no Projects panel, so the FDE panel must be added without anchoring to a nonexistent widget and without moving existing arc/history/input controls.
  Evidence: `overlay.py` now adds a lower FDE readiness area while preserving the original top HUD widget geometries.
- Pattern: local-tts-fallback-chain
  Lesson: Voice output should not depend on paid ElevenLabs credits; route TTS through ElevenLabs, optional local Kokoro/Piper, then macOS say, and raise when streaming produces zero audio so fallback actually runs.
  Evidence: `tts.py` now supports `JARVIS_TTS_PROVIDER`, `LOCAL_TTS_PROVIDER`, Piper/Kokoro commands, and tests showed explicit Piper routing plus fallback to say when local engines are missing.
- Pattern: fde-startup-nonblocking
  Lesson: Startup integrations that inspect local repos should initialize best-effort and run scans in a daemon loop with broad exception logging, so Git or path failures do not block the assistant coming online.
  Evidence: `jarvis.py` now initializes `FDETracker.load_gaps()` inside try/except and runs `scan_projects()` every 60 seconds with logged failures only.
- Pattern: mocked-provider-test-stubs
  Lesson: Routing tests that mock optional AI SDK clients should provide tiny import stubs for missing provider modules and isolate the learning DB per test, otherwise environment state can force unintended routing paths.
  Evidence: `tests/test_routing.py` stubs OpenAI/Groq/Anthropic patch targets, resets `/tmp/jarvis_test.db` in `_router()`, and the full suite passed with 31 tests.
## Reusable Lesson Template

```md
## YYYY-MM-DD Short Title

Pattern:
Fix:
Avoid:
See:
```

Use exact `Pattern:` lines for repeatable issues. When the same pattern appears 3 or more times, use `.claude/commands/promote-lesson.md` to draft a reusable skill.
## 2026-06-07 Hook Scope And SQL Safety

Pattern: hook-scope-and-sql-safety
Fix: Scope Bash safety hooks to the active repository path and test dangerous commands as synthetic hook payloads, including commands embedded inside wrappers such as `psql prod -c "TRUNCATE ..."`.
Avoid: Do not leave hooks scoped to a previous project, and do not only match `TRUNCATE` when it appears as the first shell command.
See: .claude/hooks/pre-tool-use.sh

