# JARVIS Data Inventory

Companion to [DPIA.md](DPIA.md). Records every flow of personal data that JARVIS processes, as implemented in code on 2026-09-28. Update this file whenever a tool, provider, table, or storage location is added or changed.

Legend: **Local** = stays on the Mac. **External** = leaves the machine. "Verify" = a provider term that must be confirmed against the provider's current DPA/terms before any non-personal deployment; it is not asserted here.

## 1. Data subjects

| Subject | How their data enters |
| --- | --- |
| User (operator) | Voice, typed input, screen, files, clipboard, profile facts, resume (FDE module) |
| Email correspondents | Gmail read/search/list results |
| Calendar attendees | Google Calendar events and invites |
| Contacts | iMessage/FaceTime lookups, Google contacts (read-only scope) |
| Bystanders | Ambient audio picked up by the wake-word listener and voice recording |
| People named on screen / in files / on web pages | Screenshots, file reads, browser reads |

## 2. Collection points

| Source | Code | Data | Trigger |
| --- | --- | --- | --- |
| Microphone (push-to-talk) | `jarvis/core/voice.py` | Voice audio → transcript | Hotkey / wake word |
| Microphone (wake word) | `jarvis/wake_word/stub.py` | Ambient audio chunks, transcribed locally to find "jarvis" | Continuous while running |
| HUD text box | `jarvis.py`, `jarvis/hud/overlay.py` | Typed requests | User |
| Screen | `tools/screenshot.py`, `tools/screen_vision.py`, `core/agent.py::_capture_screenshot` | Full-screen image | Tool call or vision keywords; requires `JARVIS_ALLOW_SCREEN_CAPTURE` |
| Gmail | `tools/gmail.py` (scope `gmail.modify`) | Message metadata, bodies; send/reply | Tool call; mutations need env flag + confirmation |
| Google Calendar | `tools/google_calendar.py` (scope `calendar`) | Events, attendees; create/delete | Tool call; mutations need env flag, deletes/invites need confirmation |
| Google Contacts | `tools/_google_auth.py` (scope `contacts.readonly`) | Names, emails | Tool call |
| macOS Contacts / Messages / FaceTime | `tools/system_control.py` (AppleScript) | Contact records, outgoing iMessages | Tool call; env flag + confirmation |
| Files | `tools/file_manager.py`, `tools/spotlight.py` | File contents, paths | Tool call; sensitive project paths blocked; mutations gated |
| Clipboard | `tools/clipboard.py` | Clipboard text | Tool call |
| Web | `tools/browser.py`, `tools/web_search.py` | Page text, search results | Tool call; private/local URLs blocked |
| Resume + git activity | `core/fde_analyser.py` | Resume PDF text, project summaries | Weekly (Sunday 08:00) and on demand |

## 3. Processing and recipients

| Flow | Destination | Data sent | Local/External | Control in code |
| --- | --- | --- | --- | --- |
| Speech-to-text | openai-whisper model, on device | Audio | Local | Temp WAV deleted after transcription |
| Wake-word detection | Whisper on device (Porcupine optional) | Ambient audio | Local (Porcupine access-key check: verify) | Temp WAV deleted after each chunk |
| Tier 1 reasoning | Ollama `localhost:11434` | Prompt, history, memory recall, tool output | Local | Hard-coded localhost |
| Tier 2 reasoning | Groq API (US) | Same as Tier 1 | External | Secrets redacted; untrusted output fenced |
| Tier 3 reasoning | Anthropic API (US); Groq fallback | Same, plus screenshot on vision queries | External | Same; screenshot only with env flag |
| Text-to-speech | ElevenLabs (US); macOS `say` fallback | Assistant reply text | External / Local | None beyond reply content |
| Web search | Tavily (if key), DuckDuckGo, BBC RSS | Search query | External | None |
| Weather | wttr.in | Location string, IP | External | None |
| Google APIs | Google | OAuth token, API calls | External | Scopes as listed; token stored locally |
| FDE analysis | Anthropic API | Resume text, git summaries | External | Dry-run default path |

Provider terms to verify before any non-personal deployment: training use of API data, retention period, sub-processors, transfer mechanism (SCCs / DPF), and DPA availability for Groq, Anthropic, ElevenLabs, Tavily, Picovoice.

## 4. Storage and retention

| Store | Location | Contents | Redaction | Retention |
| --- | --- | --- | --- | --- |
| Conversation memory | `data/jarvis.db` → `conversations`, `conversations_fts` | User message + assistant reply per turn | Secrets redacted (from 2026-09-28) | `memory.retention_days`, default 90; applied at startup |
| Semantic memory | `data/chroma/` | Embeddings + text of each turn | Secrets redacted | Deleted with the SQLite turn |
| User profile | `data/jarvis.db` → `user_profile` | Name, preferences, habits | None | Indefinite (no delete command yet) |
| Traces | `agent_runs`, `tool_runs` | Redacted inputs, answers, tool metadata; sensitive tool output replaced by length summary | Yes | `tracing.retention_days`, default 30; applied at startup |
| Cost usage | `model_usage` | Model, tokens, cost | Yes | Indefinite |
| Routing metrics | `routing_metrics` | Tier, latency, query text | **No** | Indefinite |
| Learning | `routing_memory`, `corrections`, `tool_failures` | Queries, bad responses, user corrections | **No** | Indefinite (reads last 7–14 days) |
| Validation failures | `validation_failures` | Tool name, params (may include email body), raw model output | **No** | Indefinite |
| FDE tracker | `fde_gaps`, `fde_build_plans`, `fde_progress`; `jarvis/data/fde_gaps.json` | Career-gap analysis, plans | n/a | Indefinite |
| Logs | `logs/jarvis.log` (+ daily rotations) | Operational events; conversation content as length placeholders | Secrets redacted | `logging.retention_days`, default 14; dir 0700, file 0600 |
| OAuth | `data/google_credentials.json`, `data/google_token.json` | Client secret, refresh token | n/a | Until revoked |
| Temp media | `/tmp/jarvis_screenshot.png`, `/tmp/jarvis_vision_shot.png`, `/tmp/jarvis_browser_shot.png` | Screen images | n/a | Overwritten on next capture; not deleted |
| Temp audio | `/tmp/jarvis_audio.wav`, `/tmp/jarvis_wake.wav`, TTS temp files | Voice audio | n/a | Deleted after use |

All of `data/`, `logs/`, `config.yaml`, `.env*`, audio and PNG files are git-ignored.

## 5. Config switches that change privacy posture

| Key / env var | Default | Effect |
| --- | --- | --- |
| `memory.retention_days` | 90 | 0 keeps conversations forever |
| `tracing.retention_days` | 30 | 0 disables trace pruning |
| `logging.retention_days` | 14 | Daily log files kept |
| `logging.conversation_content` | false | true writes transcripts/replies (redacted, 200 chars) to logs |
| `tts.provider` | auto | `say` keeps replies local |
| `JARVIS_ALLOW_*` env flags | unset | Enable shell, code, file mutation, email, calendar, screen, system, browser click |
