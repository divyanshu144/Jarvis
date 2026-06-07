# FDE Review Skill

Use this for code review, security review, maintainability review, or regression risk assessment.

## Review Priorities

1. Security and privacy risks:
   - model output reaching `shell_exec`, `code_exec`, `file_manager`
   - OAuth scopes and token handling
   - Gmail/Calendar writes
   - browser fetching and SSRF/local URL exposure
   - screenshots and screen content leakage
   - logs, data DBs, config, and secrets in Git
2. Correctness:
   - router escalation behavior
   - tool schema/executor signature drift
   - provider API assumptions
   - AppleScript escaping and subprocess argument handling
3. Maintainability:
   - duplicated tool logic
   - unclear ownership between `agent.py`, `router.py`, `registry.py`, and tool modules
   - stale README/docs
4. Tests:
   - provider calls mocked
   - dangerous system actions mocked
   - new behavior has focused coverage

## Output Standard

- Lead with findings, ordered by severity.
- Include file and line references.
- Keep summaries secondary.
- If no issues are found, state that clearly and mention residual test gaps.
