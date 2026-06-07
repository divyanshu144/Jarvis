#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
handoff="$repo_root/HANDOFF.md"
now="$(date +%s)"
window_seconds=$((30 * 60))

# Read-only sessions should not be blocked just because HANDOFF.md is absent or stale.
if [[ -z "$(git -C "$repo_root" status --porcelain 2>/dev/null || true)" ]]; then
  exit 0
fi

schema_message() {
  cat >&2 <<'MSG'
Update HANDOFF.md before ending the session with these schema fields:
- Branch
- Current Objective
- In-Flight Files
- Completed
- Verification
- Open Questions
- Risks
- Next Action
MSG
}

if [[ ! -f "$handoff" ]]; then
  echo "Stop blocked: git working tree is dirty and HANDOFF.md is missing." >&2
  echo >&2
  schema_message
  exit 2
fi

if modified_epoch="$(stat -f %m "$handoff" 2>/dev/null)"; then
  :
elif modified_epoch="$(stat -c %Y "$handoff" 2>/dev/null)"; then
  :
else
  echo "Stop blocked: git working tree is dirty and HANDOFF.md modification time could not be read: $handoff" >&2
  exit 2
fi

age=$((now - modified_epoch))
if (( age > window_seconds )); then
  cat >&2 <<MSG
Stop blocked: git working tree is dirty and HANDOFF.md has not been modified in the last 30 minutes.

File checked: $handoff
Last modified: $((age / 60)) minutes ago

MSG
  schema_message
  exit 2
fi

exit 0
