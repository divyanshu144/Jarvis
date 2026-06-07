# JARVIS Claude Code Operating Guide

This file is the project source of truth for Claude Code sessions in this repository. Read it before making changes, then use `RESOLVER.md` to pick the right workflow skill.

## Product Summary

JARVIS is a macOS desktop AI assistant with a floating PyQt HUD, voice input/output, model routing, persistent memory, and local/system tools. It can control apps, read web pages, interact with Google Gmail/Calendar, take screenshots, run shell/Python tools, and store conversational context.

The tool surface is powerful and high risk. Treat changes to routing, tool execution, OAuth, filesystem access, shell execution, browser fetching, memory, screenshots, and email/calendar actions as security-sensitive.

## Stack

- Language: Python 3.12 target, currently runnable with `python3`.
- UI: PyQt6 HUD in `jarvis/hud/`.
- Voice: PyAudio/sounddevice recording plus Whisper STT in `jarvis/core/voice.py`.
- TTS: ElevenLabs with macOS `say` fallback in `jarvis/core/tts.py`.
- AI providers: Ollama/OpenAI-compatible Tier 1, Groq Tier 2, Anthropic Claude Tier 3.
- Tools: macOS AppleScript, subprocess, browser/urllib/Playwright, Google APIs.
- Memory: SQLite at `data/jarvis.db`; optional ChromaDB under `data/chroma/`.
- Tests: pytest, mainly `tests/test_routing.py`.

## Architecture Map

- `jarvis.py`: application entrypoint, HUD startup, hotkey, wake word, proactive monitor.
- `jarvis/core/agent.py`: system prompt, memory context, routes user requests.
- `jarvis/core/router.py`: three-tier model routing and automatic tool-call loop.
- `jarvis/core/validator.py`: schema validation for tool calls. It validates shape, not safety.
- `jarvis/core/config.py`: loads `config.yaml` and environment variables.
- `jarvis/core/memory.py`: short-term, SQLite, and semantic memory.
- `jarvis/tools/registry.py`: maps LLM tool names to executor functions.
- `jarvis/tools/`: system, browser, Gmail, Calendar, shell, Python, file, clipboard, weather, music, screenshot tools.
- `jarvis/hud/overlay.py`: PyQt6 floating interface.
- `tests/test_routing.py`: mocked routing/validator/tool smoke tests.

## Commands

Setup:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Run app:

```bash
python jarvis.py
```

Google setup:

```bash
python setup_google.py
```

Targeted tests:

```bash
python3 -m pytest tests/test_routing.py -v
```

Useful read-only inspection:

```bash
rg --files
git status --short
git log -1 --oneline
```

Default verification gate:

```bash
make check
```

A project-level `Makefile` provides the default verification gate through `make check`. No `package.json`, `pyproject.toml`, lint config, or lockfile is currently present.

## Coding Conventions

- Prefer existing plain-Python module patterns over new frameworks.
- Keep tool schemas and executor signatures synchronized.
- For subprocess calls, prefer argument lists over `shell=True`; if shell use is unavoidable, justify it and contain inputs.
- Escape AppleScript strings before interpolation.
- Keep tool output short enough for model context, but never silently hide security-relevant errors.
- Tests should mock external providers, local macOS automation, network, and OAuth.
- Do not add dependencies without a clear need and user approval.
- Do not reformat unrelated files.

## Safety Rules

- Do not print, modify, delete, rotate, or commit secrets unless the user explicitly asks.
- Treat these paths as sensitive: `config.yaml`, `data/google_credentials.json`, `data/google_token.json`, `data/jarvis.db`, `data/chroma/`, `logs/`, screenshots in `/tmp`, and any OAuth/API key material.
- Treat these tools as high-risk: `shell_exec`, `code_exec`, `file_manager`, `gmail`, `google_calendar`, `browser_control`, `screenshot`, `system_control`.
- Any change that lets model output reach filesystem, shell, Python execution, OAuth APIs, browser fetching, screenshots, messages, or calendar writes needs explicit safety review.
- Avoid destructive git commands. Never run `git reset --hard`, `git checkout --`, or mass deletion unless the user clearly requests it.
- The current worktree may contain user-generated/staged files. Do not revert unrelated changes.

## Session Workflow

At session start, run:

```bash
git status --short
git log -1 --oneline
```

If `git log -1 --oneline` fails because the repository has no commits yet, record that fact in the handoff or final status.

Then inspect, in this order:

1. `HANDOFF.md`
2. `tasks/todo.md`
3. `tasks/lessons.md`
4. `CLAUDE.md`
5. `RESOLVER.md`

For implementation work:

1. Route the request to the matching `.claude/skills/*.md` workflow.
2. Inspect relevant code before editing.
3. Update `tasks/todo.md` for non-trivial work.
4. Make scoped changes only.
5. Run the narrowest meaningful verification; default to `make check` when declaring repo readiness.
6. Update `HANDOFF.md` with branch, objective, files touched, verification, risks, and next action.
7. Add durable discoveries to `tasks/lessons.md`.

## Definition Of Done

- The requested behavior or documentation exists and is project-specific.
- Run `make check` when feasible, or report exactly why it was skipped or failed.
- High-risk tool and secret implications were considered.
- Relevant tests or safe checks were run, or skipped with a concrete reason.
- `HANDOFF.md` reflects the current state.
- `tasks/todo.md` and `tasks/lessons.md` are current when the work produced useful state or lessons.
