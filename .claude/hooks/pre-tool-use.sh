#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"

parsed="$(
  PAYLOAD="$payload" python3 - <<'PY_INNER'
import json
import os

payload = os.environ.get("PAYLOAD", "")
try:
    data = json.loads(payload) if payload.strip() else {}
except json.JSONDecodeError:
    data = {}

tool = str(data.get("tool_name") or data.get("tool") or "")
tool_input = data.get("tool_input") or data.get("input") or {}
if not isinstance(tool_input, dict):
    tool_input = {}

command = str(
    tool_input.get("command")
    or data.get("command")
    or ""
)
cwd = str(
    tool_input.get("cwd")
    or data.get("cwd")
    or data.get("working_directory")
    or os.getcwd()
)

print(tool)
print(cwd)
print(command)
PY_INNER
)"

tool_name="$(printf '%s
' "$parsed" | sed -n '1p')"
cwd="$(printf '%s
' "$parsed" | sed -n '2p')"
command="$(printf '%s
' "$parsed" | sed -n '3,$p')"

case "$tool_name" in
  Bash|bash|BASH|"")
    ;;
  *)
    exit 0
    ;;
esac

case "$cwd" in
  "/Users/divyanshu/Desktop/All Projects/Jarvis"|"/Users/divyanshu/Desktop/All Projects/Jarvis"/*)
    ;;
  "/Users/divyanshu/desktop/All Projects/Jarvis"|"/Users/divyanshu/desktop/All Projects/Jarvis"/*)
    ;;
  *)
    exit 0
    ;;
esac

normalized="$(printf '%s' "$command" | tr '
' ' ' | tr '[:upper:]' '[:lower:]')"

block_reason=""

if [[ "$normalized" =~ (^|[[:space:];|&])rm[[:space:]]+(-[^[:space:]]*r[^[:space:]]*f|-rf|-fr)([[:space:]]|$) ]]; then
  block_reason="destructive recursive force delete"
elif [[ "$normalized" =~ (^|[[:space:];|&])git[[:space:]]+push([^;&|]*)(--force|-f)([[:space:]]|$) ]]; then
  block_reason="force push"
elif [[ "$normalized" =~ drop[[:space:]]+(table|database)[[:space:]] ]]; then
  block_reason="destructive SQL drop"
elif [[ "$normalized" =~ delete[[:space:]]+from[[:space:]] ]] && [[ ! "$normalized" =~ [[:space:]]where[[:space:]] ]]; then
  block_reason="DELETE FROM without WHERE"
elif [[ "$normalized" =~ truncate[[:space:]] ]] && [[ "$normalized" =~ prod|production ]]; then
  block_reason="truncate against prod/production"
fi

if [[ -n "$block_reason" ]]; then
  cat >&2 <<MSG
PreToolUse blocked unsafe Bash command: $block_reason

Command:
$command
MSG
  exit 2
fi

exit 0
