#!/usr/bin/env python3
"""
JARVIS — AI Desktop Assistant for macOS
Entry point: python jarvis.py
"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Optional

# Auto-detect Qt platform plugin path so PyQt6 finds cocoa on macOS
def _ensure_qt_plugins() -> None:
    if "QT_QPA_PLATFORM_PLUGIN_PATH" not in os.environ:
        try:
            import PyQt6
            plugin_dir = os.path.join(os.path.dirname(PyQt6.__file__), "Qt6", "plugins", "platforms")
            if os.path.isdir(plugin_dir):
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_dir
        except Exception:
            pass

_ensure_qt_plugins()

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from pynput import keyboard as _kb

from jarvis.core import privacy
from jarvis.core.agent import Agent
from jarvis.core.briefing import MorningBriefing
from jarvis.core.config import cfg
from jarvis.core.fde_tracker import FDETracker
from jarvis.core.logger import content_preview, get_logger
from jarvis.core.memory import Memory
from jarvis.core.proactive import ProactiveMonitor
from jarvis.core.tool_safety import check_tool_safety
from jarvis.core.tracing import prune_traces
from jarvis.core.tts import speak
from jarvis.core.voice import Transcriber, VoiceRecorder
from jarvis.hud.overlay import HUDBridge, HUDOverlay, Status
from jarvis.wake_word.stub import listen_for_wake_word

log = get_logger("jarvis")

_PRIVACY_NOTICE_VERSION = "v1"


def privacy_status_html() -> str:
    """One-line HUD strip: what is listening, capturing, and leaving the Mac."""
    on, off = "#ff8a5a", "#4a6a8a"
    mic = ("MIC wake word ON", on) if cfg.wake_word_enabled else ("MIC hotkey only", off)
    screen_ok = check_tool_safety("screenshot", {}).allowed
    screen = ("SCREEN capture allowed", on) if screen_ok else ("SCREEN off", off)
    cloud = ("CLOUD local-only", off) if cfg.privacy_local_only else ("CLOUD Groq/Anthropic on", on)
    return " · ".join(f'<span style="color:{c};">● {t}</span>' for t, c in (mic, screen, cloud))


def privacy_notice() -> str:
    cloud = (
        "Local-only mode is on, so email, calendar, screen and file content stays on this Mac."
        if cfg.privacy_local_only
        else "Requests the local model cannot handle go to Groq or Anthropic, and replies may be voiced by ElevenLabs."
    )
    def _keep(days: int) -> str:
        return f"{days} days" if days > 0 else "until you delete them"

    return (
        "Privacy notice. Your voice is transcribed on this Mac. "
        f"{cloud} Conversations are kept {_keep(cfg.memory_retention_days)}, "
        f"traces {_keep(cfg.trace_retention_days)} and logs {_keep(cfg.log_retention_days)}. "
        "Sending, deleting, messaging and running commands always need your confirmation. "
        "Say export my data or forget everything at any time."
    )


class JarvisApp:
    """Top-level orchestrator: voice loop + HUD + agent."""

    def __init__(self) -> None:
        self._memory = Memory()
        if cfg.trace_retention_days > 0:
            prune_traces(days_to_keep=cfg.trace_retention_days)
        self._bridge = HUDBridge()
        self._recorder = VoiceRecorder()
        self._transcriber = Transcriber()

        # Agent gets a callback to push tool names to the HUD
        self._agent = Agent(
            memory=self._memory,
            on_tool_call=self._on_tool_call,
        )

        self._voice_thread: Optional[threading.Thread] = None
        self._voice_lock = threading.Lock()  # prevents concurrent voice cycles
        self._hud: Optional[HUDOverlay] = None
        self._fde_tracker: Optional[FDETracker] = None
        self._fde_refresh_started = False
        self._init_fde_tracker()

        # First-run: ask for user name
        if not self._memory.long.get_profile("name") and not cfg.user_name:
            self._first_run_setup()

    def _privacy_notice_due(self) -> bool:
        """True once per notice version; records that the notice was shown."""
        marker = cfg.db_path.parent / f".privacy_notice_{_PRIVACY_NOTICE_VERSION}"
        if marker.exists():
            return False
        try:
            marker.write_text(time.strftime("%Y-%m-%dT%H:%M:%S"))
        except OSError as e:
            log.warning(f"Could not record privacy notice: {e}")
        return True

    def _first_run_setup(self) -> None:
        name = input("Welcome! What's your name? ").strip()
        if name:
            self._memory.long.set_profile("name", name)
            cfg.set_user_name(name)
            log.info(f"User name set to: {name}")

    def _init_fde_tracker(self) -> None:
        try:
            self._fde_tracker = FDETracker()
            result = self._fde_tracker.load_gaps()
            log.info(f"FDE tracker initialized: {result}")
        except Exception as e:
            self._fde_tracker = None
            log.warning(f"FDE tracker initialization failed; continuing startup: {e}")

    def _start_fde_refresh_loop(self) -> None:
        if self._fde_refresh_started:
            return
        self._fde_refresh_started = True

        def _loop() -> None:
            while True:
                try:
                    if self._fde_tracker is not None:
                        result = self._fde_tracker.scan_projects()
                        log.debug(f"FDE project scan refreshed: {result}")
                except Exception as e:
                    log.warning(f"FDE project scan failed; continuing: {e}")
                time.sleep(60)

        threading.Thread(target=_loop, daemon=True).start()

    # ── HUD callbacks (called from voice thread, bridge emits to Qt thread) ──

    def _set_status(self, status: str) -> None:
        self._bridge.status_changed.emit(status)

    def _set_transcript(self, text: str) -> None:
        self._bridge.transcript_changed.emit(text)

    def _set_response(self, text: str) -> None:
        self._bridge.response_changed.emit(text)

    def _on_tool_call(self, tool_name: str, tool_input: dict) -> None:
        self._bridge.tool_changed.emit(f"{tool_name}(…)")

    # ── Core interaction cycle ────────────────────────────────────────────────

    def _run_voice_cycle(self) -> None:
        """One complete listen → transcribe → think → speak cycle."""
        if not self._voice_lock.acquire(blocking=False):
            return

        try:
            # 1. Record
            self._set_status(Status.LISTENING)
            log.info("Starting recording cycle")

            if self._recorder and self._transcriber.available:
                audio = self._recorder.record(
                    on_start=lambda: self._set_status(Status.LISTENING)
                )
                if not audio:
                    self._set_status(Status.IDLE)
                    return

                # 2. Transcribe
                text = self._transcriber.transcribe(audio)
            else:
                # Fallback: text input in terminal
                text = input("[Text mode] You: ").strip() or None

            if not text:
                log.info("Nothing transcribed.")
                self._set_status(Status.IDLE)
                return

            self._set_transcript(text)
            log.info(f"User: {content_preview(text)}")

            # 3. Think + execute tools
            self._set_status(Status.THINKING)
            response = self._agent.chat(text)

            # 4. Display + speak
            self._set_response(response)
            log.info(f"JARVIS: {content_preview(response)}")
            self._set_status(Status.SPEAKING)
            speak(response)

        except Exception as e:
            log.error(f"Voice cycle error: {e}", exc_info=True)
            self._set_response(f"Error: {e}")
        finally:
            self._voice_lock.release()
            self._set_status(Status.IDLE)

    def trigger(self) -> None:
        """Trigger a voice cycle in a background thread (non-blocking)."""
        if self._hud:
            self._hud.show()
            self._hud.raise_()
        t = threading.Thread(target=self._run_voice_cycle, daemon=True)
        t.start()

    def _run_text_cycle(self, text: str) -> None:
        """Process a typed message — same pipeline as voice but skip recording."""
        if not self._voice_lock.acquire(blocking=False):
            return
        try:
            self._set_status(Status.THINKING)
            response = self._agent.chat(text)
            self._set_response(response)
            log.info(f"JARVIS (text): {content_preview(response)}")
            self._set_status(Status.SPEAKING)
            speak(response)
        except Exception as e:
            log.error(f"Text cycle error: {e}", exc_info=True)
        finally:
            self._voice_lock.release()
            self._set_status(Status.IDLE)

    def _start_global_hotkey(self) -> None:
        """Listen for Cmd+Shift+J system-wide (works even when HUD has no focus)."""
        hotkeys = {
            "<cmd>+<shift>+j": self.trigger,
            "<ctrl>+<shift>+j": self.trigger,  # fallback for non-mac
        }
        listener = _kb.GlobalHotKeys(hotkeys)
        listener.daemon = True
        listener.start()
        log.info("Global hotkey registered: Cmd+Shift+J")

    # ── Application startup ───────────────────────────────────────────────────

    def run(self) -> None:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)

        self._hud = HUDOverlay(self._bridge)
        self._hud.trigger_requested.connect(self.trigger)
        self._hud.text_submitted.connect(
            lambda text: threading.Thread(target=self._run_text_cycle, args=(text,), daemon=True).start()
        )
        self._hud.show()

        # Privacy indicators: status strip + flash on every real screen capture.
        privacy.add_capture_listener(self._bridge.capture_happened.emit)
        self._bridge.privacy_changed.emit(privacy_status_html())
        first_notice = self._privacy_notice_due()
        if first_notice:
            self._set_response(privacy_notice())

        self._start_global_hotkey()

        # Warm up Tier 1 so first voice command has no cold-start delay
        threading.Thread(target=self._agent.warmup, daemon=True).start()

        self._start_fde_refresh_loop()

        # Start wake word listener ("Hey Jarvis") unless the always-on mic is disabled.
        if cfg.wake_word_enabled:
            threading.Thread(
                target=listen_for_wake_word,
                args=(self.trigger, self._transcriber.transcribe_file, lambda: self._voice_lock.locked()),
                daemon=True,
            ).start()
        else:
            log.info("Wake word disabled (voice.wake_word: false); use the hotkey or type.")

        # Start proactive monitor (meeting alerts, battery, email notifications)
        ProactiveMonitor(
            speak_fn=speak,
            is_busy=lambda: self._voice_lock.locked(),
        ).start()

        # Morning briefing — auto-delivers if it's 6–11am
        self._briefing = MorningBriefing(
            speak_fn=speak,
            is_busy=lambda: self._voice_lock.locked(),
        )
        self._briefing.check_startup()

        # The first-run privacy notice is shown in the HUD only; just the greeting is spoken.
        log.info("JARVIS is online. Say 'Hey Jarvis' or press Cmd+Shift+J to trigger.")
        greeting = f"JARVIS online. How can I help you{', ' + cfg.user_name if cfg.user_name else ''}?"

        def _greet() -> None:
            # speak() blocks, so it must not run on the Qt thread: the HUD only paints once
            # app.exec() starts. Holding the voice lock stops the wake word hearing JARVIS.
            with self._voice_lock:
                speak(greeting)

        threading.Thread(target=_greet, daemon=True).start()

        sys.exit(app.exec())


def main() -> None:
    if not cfg.anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        print("Add it to config.yaml or set the ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)

    jarvis = JarvisApp()
    jarvis.run()


if __name__ == "__main__":
    main()
