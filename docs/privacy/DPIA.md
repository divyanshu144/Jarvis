# Data Protection Impact Assessment — JARVIS

| Field | Value |
| --- | --- |
| System | JARVIS macOS desktop AI assistant (this repository) |
| Version assessed | `master` @ 43dd037 + uncommitted privacy hardening, 2026-09-28 |
| Method | GDPR Art. 35(7); UK ICO nine-step DPIA process; EDPB WP248 rev.01 screening criteria |
| Data inventory | [data_inventory.md](data_inventory.md) |
| Owner / sign-off | Project owner (divyanshu144) |
| Status | v1.1 — signed off by owner for personal use (context A), verified 2026-09-28; must be re-run by the controller before any shared or client deployment |
| Next review | 2027-03-28, or earlier on any trigger in §9 |

This is an engineering DPIA, not legal advice. Items marked "verify" need confirmation against current provider terms or by counsel/DPO.

---

## 1. Need for a DPIA (screening)

**Deployment contexts**

| Context | Legal position | DPIA |
| --- | --- | --- |
| A. Owner's personal Mac, personal use | GDPR household exemption (Art. 2(2)(c)) likely applies; India DPDP Act 2023 personal/domestic exemption likely applies | Not legally mandatory; done as good practice and to prepare for B |
| B. Deployed to employees, clients, or the public | Deployer is controller; JARVIS processes third-party communications | **Mandatory** — meets ≥2 WP248 criteria (below) |

**WP248 criteria met (context B)**

| # | Criterion | Met | Why |
| --- | --- | --- | --- |
| 1 | Evaluation / scoring | Partly | Learned user profile, corrections, FDE career-gap scoring |
| 2 | Automated decisions with legal/similar effect | No | Actions are user-requested; high-impact ones need confirmation |
| 3 | Systematic monitoring | **Yes** | Always-on wake-word microphone, screen capture, proactive monitor |
| 4 | Sensitive or highly personal data | **Yes** | Email, iMessage, calendar, contacts, files, clipboard; special-category data can appear incidentally in email |
| 5 | Large scale | No (A) / depends (B) | Single user per install |
| 6 | Matching / combining datasets | **Yes** | Email + calendar + contacts + memory + profile combined per request |
| 7 | Vulnerable data subjects | Possible | Employees in context B (power imbalance) |
| 8 | Innovative technology | **Yes** | LLM agent with autonomous tool use |
| 9 | Prevents exercise of rights / access to a service | No | — |

Result: 4 criteria clearly met → DPIA required for context B.

## 2. Description of the processing

**Nature.** A user speaks or types a request. It is transcribed on device (Whisper), combined with recent history, recalled memory, and profile facts, and sent to a model tier: local Ollama first, then Groq, then Anthropic. The model may call tools (Gmail, Calendar, iMessage, files, browser, shell, screen). Tool output is fed back to the model. The reply is shown in the HUD and spoken (ElevenLabs or macOS `say`). The turn is stored in memory; metadata is traced.

**Scope.** See [data_inventory.md](data_inventory.md) for every data category, subject, store, recipient, and retention period. Summary:

- Subjects: user, email correspondents, calendar attendees, contacts, bystanders (audio), people visible on screen or in files.
- Data: voice, transcripts, email/message content, calendar events, contacts, files, clipboard, screen images, web content, profile facts, resume, git activity.
- External recipients: Groq, Anthropic, ElevenLabs, Tavily, DuckDuckGo, BBC, wttr.in, Google. US-based processors → international transfer in context B.
- Retention: conversations 90 days, traces 30 days, logs 14 days, profile indefinite (configurable, see inventory §5).

**Context.** Single-user macOS app with deep OS integration. Users reasonably expect an assistant to read their email when asked; correspondents and bystanders do not expect their content to reach US AI providers. LLMs are susceptible to prompt injection from content they read.

**Purposes.** Voice/desktop assistance: answering questions, summarising and acting on email/calendar, controlling apps and system settings, file and web tasks, proactive reminders, and personal career-readiness tracking (FDE module).

## 3. Consultation

| Stakeholder | Method | Status |
| --- | --- | --- |
| Owner/user | This assessment; guardrail review 2026-09-28 | Done |
| Security review | Model-to-tool trust boundary review (`.claude/skills/fde-review.md`) | Done for tool gating, confirmation, injection, logging |
| Third parties (correspondents, contacts, bystanders) | Not directly consultable; interests represented via minimisation, no-training verification, retention | Represented |
| DPO / counsel | Required before context B | Open |
| Processors | Review DPAs and data-use terms (Groq, Anthropic, ElevenLabs, Tavily, Picovoice) | Open — verify |

## 4. Necessity and proportionality

| Principle | Assessment |
| --- | --- |
| Lawful basis (A) | Household exemption |
| Lawful basis (B) | User data: contract or legitimate interests. Third-party data in email/calendar: legitimate interests, requires a documented LIA. Special-category data appearing in email: no Art. 9 condition for deliberate processing, so minimise — not persisted in traces, redacted/expiring memory; open item to avoid profiling on it |
| Purpose limitation | Tools act only on user requests; FDE module uses only the owner's resume and repos |
| Minimisation | Local STT and local Tier 1 first; sensitive tool output never stored in traces; logs store content length only; Google contacts read-only. **Gaps:** full tool output reaches cloud tiers; broad Gmail/Calendar scopes |
| Accuracy | Model output can be wrong; high-impact actions need confirmation; corrections loop |
| Storage limitation | Retention for conversations, derived tables, traces, logs, temp audio. **Gaps:** profile indefinite; temp screenshots overwritten, not deleted |
| Integrity / confidentiality | Secrets redacted everywhere text is persisted or sent; files git-ignored; logs 0600; sensitive paths blocked from file tool; secret-free subprocess env. **Gap:** `data/jarvis.db` not encrypted at rest (relies on FileVault) |
| Transparency | **Gap:** no in-app privacy notice, no mic/capture indicator |
| Data subject rights | **Gap:** no export or "forget" command; deletion is manual (delete `data/`) |
| International transfers (B) | Groq, Anthropic, ElevenLabs, Tavily are US → SCCs/DPF, verify |
| Processors | DPAs needed in context B — verify |

## 5. Risks

Likelihood (L) and severity (S) scored 1 (remote/minimal) to 3 (probable/severe). Inherent = before controls; residual in §6.

| ID | Risk to individuals | Source | L | S | Inherent |
| --- | --- | --- | --- | --- | --- |
| R1 | Prompt injection in an email or web page makes the agent send, forward, or delete data | LLM tool loop | 3 | 3 | **High** |
| R2 | Third-party email/calendar/screen content sent to US AI providers and retained or used for training | Tier 2/3, ElevenLabs | 3 | 2 | **High** |
| R3 | Plaintext transcripts and replies accumulate in logs and DB tables indefinitely | Logging, metrics, learning, validator | 3 | 2 | **High** |
| R4 | Bystander speech recorded and transcribed by the always-on wake word | Wake-word listener | 3 | 2 | **High** |
| R5 | Unintended screen capture sent to Claude (keyword match, e.g. "screenshot") | Agent vision path | 2 | 3 | **High** |
| R6 | API keys or tokens leak via traces, memory, logs, or model context | Tool output, user input | 2 | 3 | **High** |
| R7 | Model-driven shell/code destroys data or exfiltrates secrets | `shell_exec`, `code_exec` | 2 | 3 | **High** |
| R8 | Wrong recipient or content in a sent email/iMessage | Model error | 2 | 2 | Medium |
| R9 | User cannot see or delete what JARVIS remembers | No rights tooling | 3 | 1 | Medium |
| R10 | OAuth token theft gives full mailbox/calendar access | Broad scopes, token on disk | 1 | 3 | Medium |
| R11 | Profiling: learned profile and corrections build a behavioural record | Memory, learning | 2 | 1 | Low |
| R12 | Local DB/Chroma readable by other local processes or backups | Unencrypted SQLite | 1 | 2 | Low |

## 6. Measures and residual risk

| ID | Measures in place (code) | Residual | Further action |
| --- | --- | --- | --- |
| R1 | Per-action user confirmation for send/reply/iMessage/FaceTime/empty-Trash/calendar delete+invite/file delete+move+overwrite and all shell/code execution, confirmed only from raw user input (`core/confirmation.py`); env-flag gating per capability (`core/tool_safety.py`); untrusted output fenced + prompt rules (`core/router.py`, `core/agent.py`); private-URL block | **Low** | — |
| R2 | Local Whisper; local Tier 1 first; secrets redacted before any tier; **local-only mode** (`privacy.local_only` / `JARVIS_LOCAL_ONLY=1`) withholds Gmail/Calendar/screen/file/clipboard/Spotlight/shell/code output and previews from Groq/Anthropic, blocks `screen_vision`, skips screenshot attachment, forces local TTS (`core/router.py`, `core/tts.py`, `core/tool_safety.py`) | **Low** with local-only on; **Medium** with it off (context A default, accepted) | A6 provider terms; context B must run with local-only on |
| R3 | Content placeholders in logs, redaction filter, daily rotation, 14-day log retention, 0600/0700 perms (`core/logger.py`); redaction on write + 90-day retention for conversations and derived tables (`core/memory.py`); one-off redaction of pre-existing rows, embeddings and logs (`core/privacy.py::redact_existing_data`, CLI `redact-existing`) | **Low** | — |
| R4 | Transcription on device; ambient WAV deleted after each chunk; transcript not logged; HUD strip shows "MIC wake word ON"; `voice.wake_word: false` disables the always-on mic | **Low** | Prefer Porcupine (keyword-only) over Whisper fallback when a key is available |
| R5 | Capture requires `JARVIS_ALLOW_SCREEN_CAPTURE`; HUD flashes "SCREEN CAPTURED" on every real capture; temp screenshots deleted at the end of each request and after `screen_vision` reads them | **Low** | — |
| R6 | Redaction in traces, memory, logs, derived tables, model context; secret-free subprocess env; sensitive paths blocked; git-ignore; OAuth token file 0600 | **Low** | Regex redaction is best-effort; add patterns as providers are added |
| R7 | Off by default; per-action confirmation; hardened denylist; secret-free env; `python3 -I` in temp dir | **Low** | — |
| R8 | Confirmation prompt reads recipient/subject/message aloud before sending | **Low** | — |
| R9 | "Export my data" (JSON in `data/exports/`, 0600) and "forget everything" (confirmed; deletes conversations, FTS, profile, traces, derived tables, Chroma, logs, then VACUUM) by voice or `python3 -m jarvis.tools.privacy_cli`; first-run privacy notice | **Low** | — |
| R10 | Least-privilege scopes `gmail.readonly` + `gmail.send` + `calendar.events` (no `gmail.modify`, full calendar, or contacts); old broad token refused and revoked by `setup_google.py`; token 0600 | **Low** | Owner re-runs `python setup_google.py` once |
| R11 | Profile limited to explicit facts; corrections expire; profile deleted by "forget everything" | **Low** | — |
| R12 | Git-ignored; relies on FileVault | **Low** | Document FileVault requirement for context B |

No residual risk is rated High. With local-only mode off (owner's default), R2 stays Medium and is accepted in §8. Context A: acceptable. Context B: acceptable only with local-only mode on, A6 completed, and a DPO review; otherwise prior consultation with the supervisory authority (Art. 36) should be considered for R2.

## 7. Action plan

| ID | Action | Risks | Priority | Status |
| --- | --- | --- | --- | --- |
| A1 | Local-only mode: keep Gmail/Calendar/screen/file/clipboard output on Tier 1, local TTS | R2 | High | Implemented 2026-09-28 (opt-in) |
| A2 | "Forget everything" and "export my data" commands (conversations, profile, traces, Chroma, logs) | R9, R11 | High | Implemented 2026-09-28 |
| A3 | HUD privacy strip (mic / screen / cloud), capture flash, first-run privacy notice, wake-word off switch | R4, R5, transparency | High | Implemented 2026-09-28 |
| A4 | Least-privilege OAuth scopes; `mark_read` removed (owner decision) | R10 | Medium | Implemented 2026-09-28 — owner must re-run `setup_google.py` |
| A5 | Per-action confirmation for `shell_exec` / `code_exec` | R1, R7 | Medium | Implemented 2026-09-28 |
| A6 | Verify and record training-use, retention, sub-processor, and transfer terms for Groq, Anthropic, ElevenLabs, Tavily, Picovoice in `processors.md` | R2 | High (context B) | Open — research not yet completed |
| A7 | Delete `/tmp` screenshots after the request completes | R5 | Low | Implemented 2026-09-28 |
| A8 | Redact pre-2026-09-28 rows, embeddings and logs, keeping history (owner decision) | R3 | Low | Done 2026-09-28 (348 log lines redacted; DB had no secrets; Chroma not installed) |
| A9 | Add DPIA review to pre-push checklist | All | Medium | Done (`.claude/skills/pre-push-checklist.md`) |
| — | Per-action confirmation, injection fencing, egress redaction | R1, R6 | — | Done 2026-09-28 |
| — | Memory/log/derived-table redaction and retention, temp-audio deletion | R3, R4 | — | Done 2026-09-28 |
| — | Screenshot gate, hardened shell denylist, secret-free exec env | R5, R7 | — | Done 2026-09-28 |

## 8. Sign-off

| Item | Decision |
| --- | --- |
| Measures approved by | Project owner (divyanshu144), 2026-09-28, instructed in the working session |
| Residual risk accepted (context A) | Yes, by the owner. Includes R2 at Medium while local-only mode is off. |
| Owner decisions recorded | A4: narrow scopes and drop `mark_read`. A8: redact existing data and keep history. |
| Verification status | 2026-09-28: `make check` 192 passed, including end-to-end flows through the real Agent/Router/registry/safety/tracing/memory stack (`tests/test_e2e_flows.py`). HUD privacy strip and capture flash verified with real PyQt6 widgets offscreen. A8 run on live data: 348 log lines redacted, 0 remaining, DB row counts unchanged, FTS integrity ok. E2E testing found and fixed one gap: user-typed secrets reached model tiers and rolling history (now redacted). Not yet run by the owner: live HUD/voice session, `setup_google.py` re-auth. |
| DPO advice (context B) | Not yet sought |
| Supervisory authority consultation needed | No for A; reassess for B after local-only on, A6, DPO review |

## 9. Review triggers

Re-run the affected sections of this DPIA, and update `data_inventory.md`, when any of these happens:

- A new tool, model provider, TTS/STT provider, or external API is added.
- A new store, table, or file that holds user or third-party content is added.
- A retention default, OAuth scope, env-flag default, or confirmation rule changes.
- JARVIS is shared with anyone other than the owner (moves to context B).
- A privacy or security incident occurs.
- Scheduled review date is reached.

Verification evidence for the controls above: `tests/test_privacy_guardrails.py`, `tests/test_logging_privacy.py`, `tests/test_dpia_actions.py`, `tests/test_e2e_flows.py`, `tests/test_tracing.py`; `make check` passed (192 tests) on 2026-09-28.
