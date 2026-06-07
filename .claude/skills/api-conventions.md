# API And Tool Conventions Skill

Use this for backend/API/provider/tool schema work, including Google APIs, browser fetching, router model calls, and frontend-HUD contracts.

## Tool Schema Rules

- Every tool exposed in `TOOL_DEFINITIONS` must have a matching executor in `jarvis/tools/registry.py`.
- Keep JSON schema required fields aligned with executor defaults.
- Use enums for constrained actions.
- Validate shape in `validator.py`, but implement safety policy separately.
- Return concise strings; avoid leaking secrets, full tokens, raw credentials, or excessive email/body content.

## Provider And Router Rules

- Tier 1 uses OpenAI-compatible Ollama.
- Tier 2 uses Groq with OpenAI-compatible tool definitions.
- Tier 3 uses Anthropic tools, with Groq fallback.
- Provider tests should mock SDK clients.
- Changes to escalation, tool iteration, or tool result truncation need routing tests.

## Local/System API Rules

- Prefer subprocess argument lists over `shell=True`.
- Escape all AppleScript interpolated strings.
- Browser fetches should validate schemes and consider host allow/deny policy.
- File operations should be path-scoped unless the user explicitly requested broad system access.
- Gmail/Calendar writes need confirmation or a clear approval gate for risky/bulk actions.

## HUD Contract Rules

- HUD updates flow through `HUDBridge` signals.
- Avoid blocking Qt thread work.
- Long-running actions should stay in background threads.
- Status changes should remain consistent with `Status` values in `jarvis/hud/overlay.py`.
