# JARVIS Conventions Skill

Use this when a request asks where code should live, how to follow project patterns, how to wire config, or how to avoid architecture drift.

## Core Invariants

- All environment variables, API keys, and secret fallback logic must go through `jarvis/core/config.py` and the shared `cfg` object.
- Do not read `os.environ` directly from tools, agents, router code, HUD code, or analyzers unless the config module is being changed.
- Tool schemas in `jarvis/tools/registry.py` must match executor names, required parameters, defaults, and accepted enum values.
- High-risk tools must go through `jarvis/core/tool_safety.py` before executor invocation through the shared registry dispatch path.
- Provider/API calls in tests must be mocked. Do not call OpenAI, Anthropic, Groq, Google APIs, browser automation, screenshots, microphone, or macOS automation in unit tests.
- Subprocess calls should use argument lists. Avoid `shell=True`; if unavoidable, explain why and constrain inputs.
- AppleScript strings must be escaped before interpolation.
- GUI, microphone, wake word, and audio/TTS verification must be explicitly reported as either run or skipped with a reason.

## Placement Rules

- App startup and orchestration: `jarvis.py`.
- Agent prompt and memory context: `jarvis/core/agent.py`.
- Model routing and provider escalation: `jarvis/core/router.py`.
- Tool definitions and shared dispatch: `jarvis/tools/registry.py`.
- Tool execution logic: one focused module under `jarvis/tools/`.
- Safety policy: `jarvis/core/tool_safety.py`.
- Config/secrets/env access: `jarvis/core/config.py`.
- PyQt HUD UI/state: `jarvis/hud/overlay.py`.
- Voice/STT/TTS: `jarvis/core/voice.py`, `jarvis/core/tts.py`, `jarvis/wake_word/`.

## Verification Expectations

- Run `make check` for repo-level readiness when feasible.
- For routing/tool schema changes, run `python3 -m pytest tests/test_routing.py -v` at minimum.
- For HUD/audio changes, state whether full app verification was run and what dependencies or permissions were required.
