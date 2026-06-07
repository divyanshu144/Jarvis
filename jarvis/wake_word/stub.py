"""
Wake word detection — two implementations, chosen at runtime:
  1. Porcupine (pvporcupine) — precise, low-CPU, uses "jarvis" built-in keyword.
     Requires PICOVOICE_ACCESS_KEY in config or environment.
  2. Whisper VAD — fallback, no extra key needed.
"""

from __future__ import annotations

import io
import math
import struct
import time
import wave
from typing import Callable

from jarvis.core.logger import get_logger

log = get_logger(__name__)

_TMP_PATH = "/tmp/jarvis_wake.wav"

# ── Porcupine (preferred) ────────────────────────────────────────────────────

def _listen_porcupine(
    on_detected: Callable,
    is_busy: Callable[[], bool],
    access_key: str,
) -> None:
    try:
        import pvporcupine
        import pyaudio
    except ImportError:
        raise ImportError("pvporcupine not installed")

    log.info("Wake word: using Porcupine ('jarvis' keyword).")
    porcupine = pvporcupine.create(access_key=access_key, keywords=["jarvis"])
    pa = pyaudio.PyAudio()
    stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length,
    )
    try:
        while True:
            if is_busy():
                time.sleep(0.1)
                continue
            pcm_bytes = stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from(f"{porcupine.frame_length}h", pcm_bytes)
            if porcupine.process(pcm) >= 0 and not is_busy():
                log.info("Wake word detected (Porcupine).")
                on_detected()
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        porcupine.delete()


# ── Whisper VAD (fallback) ───────────────────────────────────────────────────

_CHUNK = 1024
_CHANNELS = 1
_RATE = 16000
_RECORD_SECONDS = 2
_RMS_THRESHOLD = 200


def _listen_whisper(
    on_detected: Callable,
    transcribe_fn: Callable[[str], dict],
    is_busy: Callable[[], bool],
) -> None:
    try:
        import pyaudio
    except ImportError:
        log.warning("PyAudio not installed — wake word detection unavailable.")
        return

    log.info("Wake word: using Whisper VAD (say 'Hey Jarvis').")
    pa = pyaudio.PyAudio()

    while True:
        try:
            if is_busy():
                time.sleep(0.3)
                continue

            stream = pa.open(
                format=pyaudio.paInt16,
                channels=_CHANNELS,
                rate=_RATE,
                input=True,
                frames_per_buffer=_CHUNK,
            )

            frames = []
            total_rms = 0.0
            num_chunks = int(_RATE / _CHUNK * _RECORD_SECONDS)

            try:
                for _ in range(num_chunks):
                    if is_busy():
                        break
                    data = stream.read(_CHUNK, exception_on_overflow=False)
                    frames.append(data)
                    shorts = struct.unpack(f"{len(data) // 2}h", data)
                    rms = math.sqrt(sum(x * x for x in shorts) / len(shorts)) if shorts else 0.0
                    total_rms += rms
            finally:
                stream.stop_stream()
                stream.close()

            if not frames or is_busy():
                continue

            avg_rms = total_rms / max(len(frames), 1)
            if avg_rms < _RMS_THRESHOLD:
                continue

            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(_CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(_RATE)
                wf.writeframes(b"".join(frames))
            with open(_TMP_PATH, "wb") as f:
                f.write(buf.getvalue())

            result = transcribe_fn(_TMP_PATH)
            text = result.get("text", "").lower().strip()

            if "jarvis" in text and not is_busy():
                log.info(f"Wake word detected (Whisper): {text!r}")
                on_detected()

        except Exception as e:
            log.warning(f"Wake word listener error: {e}")


# ── Public entry point ────────────────────────────────────────────────────────

def listen_for_wake_word(
    on_detected: Callable,
    transcribe_fn: Callable[[str], dict],
    is_busy: Callable[[], bool],
) -> None:
    """
    Block forever — call in a daemon thread.
    Tries Porcupine first (if key configured), falls back to Whisper VAD.
    """
    from jarvis.core.config import cfg
    key = cfg.picovoice_key
    if key:
        try:
            _listen_porcupine(on_detected, is_busy, key)
            return
        except ImportError:
            log.info("pvporcupine not installed — falling back to Whisper VAD.")
        except Exception as e:
            log.warning(f"Porcupine failed ({e}) — falling back to Whisper VAD.")

    if transcribe_fn is None:
        log.warning("No transcribe function — wake word detection unavailable.")
        return

    _listen_whisper(on_detected, transcribe_fn, is_busy)
