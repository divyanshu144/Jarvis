# JARVIS - AI Desktop Assistant for macOS

A floating macOS AI assistant with voice I/O, a PyQt6 HUD, three-tier model routing, local/system tools, Google integrations, proactive monitoring, and persistent memory.

## Quick Start

### 1. Prerequisites

```bash
# System dependencies
brew install portaudio ffmpeg

# Python 3.12
brew install python@3.12
```

### 2. Install Python dependencies

```bash
cd Jarvis
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### 3. Configure API keys

Edit `config.yaml`:

```yaml
api_keys:
  anthropic: "sk-ant-..."
  elevenlabs: "..."      # optional — falls back to macOS say
  tavily: "..."          # optional — web search tool disabled if missing
```

Or set environment variables:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export ELEVENLABS_API_KEY="..."
export TAVILY_API_KEY="..."
```

### 4. Run

```bash
python jarvis.py
```

On first run it will ask for your name and load Whisper (downloads ~150 MB for `base` model).

## Triggering JARVIS

| Method | Action |
|--------|--------|
| **Cmd+Shift+J** | Start listening (keyboard shortcut) |
| **Double-click HUD** | Toggle HUD visibility |
| **Text mode** | Automatic fallback if PyAudio/Whisper unavailable |

## Available Tools

| Tool | What it does |
|------|--------------|
| `apple_music` | Play, pause, search, skip, shuffle, repeat, volume for Apple Music |
| `app_control` | Open / close / switch macOS apps via AppleScript |
| `browser_control` | Navigate URLs, read page content, click elements |
| `calendar` | Read / create macOS Calendar events |
| `clipboard` | Read / write macOS clipboard |
| `code_exec` | Write and run Python code, blocked by default through model dispatch |
| `file_manager` | Read, write, move, delete, search files, with sensitive path/mutation gates |
| `gmail` | List, read, search, send, reply, mark read, unread count |
| `google_calendar` | Today's agenda, upcoming events, create/delete, free-time search |
| `screen_vision` | Capture screen and ask Claude vision about it, blocked by default |
| `screenshot` | Capture screen, blocked by default through model dispatch |
| `shell_exec` | Run zsh commands, blocked by default through model dispatch |
| `spotlight` | Search local files with Spotlight and optionally open first result |
| `system_control` | Volume, brightness, Focus, iMessage, reminders, notes, maps, FaceTime, media |
| `system_info` | Battery, WiFi, CPU, memory, disk stats |
| `timer` | Timers with notification and spoken completion |
| `weather` | Current weather and forecast using wttr.in |
| `web_search` | Tavily search when configured, BBC/DuckDuckGo fallback otherwise |

## Routing

JARVIS routes each request through a three-tier cascade:

1. Tier 1: local Ollama OpenAI-compatible model for quick/simple commands.
2. Tier 2: Groq fallback for cloud routing/tool use.
3. Tier 3: Claude Sonnet for vision, complex work, and final fallback, with Groq fallback if Claude is unavailable.

Routing behavior lives in `jarvis/core/router.py`. Tool calls are validated for schema shape in `jarvis/core/validator.py`, then dispatched through `jarvis/tools/registry.py`.

## Safety Gates

Model-invoked high-risk tools are gated in `jarvis/core/tool_safety.py`.

Blocked by default unless explicitly enabled for an approved local session:

```bash
export JARVIS_ALLOW_SHELL_EXEC=1
export JARVIS_ALLOW_CODE_EXEC=1
export JARVIS_ALLOW_FILE_MUTATION=1
export JARVIS_ALLOW_EMAIL_MUTATION=1
export JARVIS_ALLOW_CALENDAR_MUTATION=1
export JARVIS_ALLOW_SCREEN_CAPTURE=1
export JARVIS_ALLOW_SYSTEM_MUTATION=1
```

The safety policy also blocks dangerous shell patterns, sensitive runtime paths under `data/` and `logs/`, local/private browser URLs, and destructive email/calendar/system actions unless explicitly allowed.

Direct module-level executor tests may still exercise tools directly; the gate is enforced at model dispatch time.

## Memory

- **Short-term**: last 20 message turns in RAM
- **Long-term**: SQLite at `data/jarvis.db`
- **Semantic**: ChromaDB embeddings at `data/chroma/` — top-3 similar past conversations injected per query

## HUD Colors

| Color | Meaning |
|-------|---------|
| Blue `#00d4ff` | Listening |
| Orange `#f5a623` | Thinking / calling Claude |
| Purple `#bd10e0` | Executing tool |
| Green `#7ed321` | Speaking response |
| Dark | Idle |

## Adding Wake Word (optional)

1. Go to [console.picovoice.ai](https://console.picovoice.ai)
2. Train a "Hey JARVIS" wake word model (free), download the `.ppn` file
3. Update `config.yaml`:
   ```yaml
   wake_word:
     enabled: true
     ppn_path: "/path/to/hey-jarvis.ppn"
     access_key: "your-picovoice-key"
   ```
4. See `jarvis/wake_word/stub.py` for the implementation template

## Project Structure

```
jarvis/
├── jarvis.py              # Entry point
├── config.yaml            # All configuration
├── requirements.txt
├── jarvis/
│   ├── core/
│   │   ├── agent.py       # Agent prompt, memory context, route call
│   │   ├── config.py      # Config loader
│   │   ├── learning.py    # Routing/correction learning
│   │   ├── logger.py      # Structured logging
│   │   ├── memory.py      # Short/long-term + semantic memory
│   │   ├── metrics.py     # Routing metrics
│   │   ├── proactive.py   # Calendar/battery/email proactive monitor
│   │   ├── router.py      # 3-tier model routing + tool loop
│   │   ├── tool_safety.py # Model-invoked tool safety policy
│   │   ├── tts.py         # ElevenLabs / say TTS
│   │   ├── validator.py   # Tool schema validation
│   │   └── voice.py       # PyAudio recording + Whisper STT
│   ├── tools/
│   │   ├── registry.py    # Tool dispatcher
│   │   ├── apple_music.py
│   │   ├── app_control.py
│   │   ├── browser.py
│   │   ├── calendar_tool.py
│   │   ├── clipboard.py
│   │   ├── code_exec.py
│   │   ├── file_manager.py
│   │   ├── gmail.py
│   │   ├── google_calendar.py
│   │   ├── screen_vision.py
│   │   ├── screenshot.py
│   │   ├── shell.py
│   │   ├── spotlight.py
│   │   ├── system_control.py
│   │   ├── system_info.py
│   │   ├── timer_tool.py
│   │   ├── weather.py
│   │   └── web_search.py
│   ├── hud/
│   │   └── overlay.py     # PyQt6 floating HUD
│   └── wake_word/
│       └── stub.py        # Wake word stub (pvporcupine template)
├── data/                  # Auto-created: SQLite + ChromaDB
└── logs/jarvis.log
```
