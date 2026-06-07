# Promote Lesson

Use this command to turn repeated lessons from `tasks/lessons.md` into a reusable project skill.

## Goal

Read `tasks/lessons.md`, find lesson patterns that appear 3 or more times by exact `Pattern:` field value, draft a new skill file for `.claude/skills/`, and propose the matching `RESOLVER.md` keyword to skill mapping.

## Hard Stop Rule

Always stop for human approval before writing anything. Do not create, edit, move, or delete files during this command unless the user explicitly approves the exact proposed changes after reviewing the draft.

## Workflow

1. Read:
   - `tasks/lessons.md`
   - `RESOLVER.md`
   - existing `.claude/skills/*.md`
2. Extract every exact `Pattern:` value from `tasks/lessons.md`. Count only lines that begin with `Pattern:` exactly, ignoring bullets such as `- Pattern:` and ignoring prose mentions.
3. Count occurrences by exact pattern value after trimming whitespace after `Pattern:`.
4. Select only patterns with 3 or more occurrences.
5. If no pattern qualifies, report:
   - "No promotable lesson patterns found."
   - the observed pattern counts
   - that no files will be changed
6. For each qualifying pattern, draft:
   - proposed skill filename under `.claude/skills/`
   - proposed skill title
   - trigger conditions
   - workflow steps
   - verification expectations
   - safety notes
   - proposed `RESOLVER.md` request keyword or row mapping
7. Present the draft and ask for approval.
8. Stop. Wait for explicit human approval before writing any file.

## Draft Format

```text
Promotable pattern: <pattern>
Occurrences: <count>

Proposed skill file:
.claude/skills/<name>.md

Proposed skill content:
<draft markdown>

Proposed RESOLVER.md mapping:
<request type or keyword> -> .claude/skills/<name>.md

Approval needed:
Reply with approval to write these changes, or provide edits.
```

## Constraints

- Do not overwrite existing useful skills.
- If a proposed filename already exists, propose a merge plan instead of replacing it.
- Keep the skill project-specific to JARVIS unless the repeated lesson clearly applies to the shared Claude workflow.
- Treat sensitive paths and high-risk tools according to `CLAUDE.md`.
