"""
Voice input pipeline:
  - Record from microphone until silence
  - Transcribe with OpenAI Whisper (local)
  - Falls back to text input if Whisper or PyAudio unavailable
"""

from __future__ import annotations

import io
import math
import threading
import time
import wave
from pathlib import Path
from typing import Callable

from jarvis.core.config import cfg
from jarvis.core.logger import get_logger

log = get_logger(__name__)

_WHISPER_AVAILABLE = False
_PYAUDIO_AVAILABLE = False

try:
    import whisper as _whisper
    _WHISPER_AVAILABLE = True
except ImportError:
    log.warning("openai-whisper not installed — voice input unavailable.")

try:
    import pyaudio as _pyaudio
    _PYAUDIO_AVAILABLE = True
except ImportError:
    log.warning("PyAudio not installed — voice input unavailable.")


def _find_input_device(pa) -> tuple[int | None, int]:
    """Return (device_index, sample_rate) for the best available mic."""
    import struct, math as _math
    preferred_names = ["macbook air microphone", "built-in microphone", "iphone microphone"]
    candidates: list[tuple[int, int]] = []

    for i in range(pa.get_device_count()):
        d = pa.get_device_info_by_index(i)
        if d["maxInputChannels"] < 1:
            continue
        rate = int(d["defaultSampleRate"])
        name = d["name"].lower()
        # prefer by name
        priority = next((j for j, n in enumerate(preferred_names) if n in name), 99)
        candidates.append((priority, i, rate))

    candidates.sort()
    for _, idx, rate in candidates:
        # quick sanity: can we open it and get non-zero data?
        try:
            s = pa.open(format=pa.get_format_from_width(2), channels=1,
                        rate=rate, input=True, input_device_index=idx,
                        frames_per_buffer=1024)
            data = s.read(1024, exception_on_overflow=False)
            s.stop_stream(); s.close()
            shorts = struct.unpack(f"{len(data)//2}h", data)
            rms = _math.sqrt(sum(x*x for x in shorts) / len(shorts)) if shorts else 0
            if rms > 0:
                log.info(f"Selected mic: [{idx}] ambient_rms={rms:.0f}  rate={rate}")
                return idx, rate
        except Exception:
            continue

    # give up — let PyAudio pick the default
    return None, 16000


class VoiceRecorder:
    """Records audio until silence, returns raw PCM bytes."""

    CHUNK = 1024
    CHANNELS = 1

    def __init__(self) -> None:
        self._silence_thresh = cfg.silence_threshold
        self._silence_dur = cfg.silence_duration
        self._device_idx: int | None = None
        self._rate: int = cfg.sample_rate
        self._pa = None
        if _PYAUDIO_AVAILABLE:
            import pyaudio
            self._pa = pyaudio.PyAudio()
            self._device_idx, self._rate = _find_input_device(self._pa)

    def _rms(self, data: bytes) -> float:
        import struct
        count = len(data) // 2
        shorts = struct.unpack(f"{count}h", data)
        if count == 0:
            return 0.0
        mean_sq = sum(s * s for s in shorts) / count
        return math.sqrt(mean_sq)

    def record(self, on_start: Callable | None = None) -> bytes | None:
        """
        Block until the user speaks, then record until silence.
        Returns raw PCM bytes or None on failure.
        """
        if not _PYAUDIO_AVAILABLE or self._pa is None:
            return None
        import pyaudio

        pa = self._pa

        stream = pa.open(
            format=pyaudio.paInt16,
            channels=self.CHANNELS,
            rate=self._rate,
            input=True,
            input_device_index=self._device_idx,
            frames_per_buffer=self.CHUNK,
        )
        # Skip first 0.5s to let keyboard-shortcut click noise pass
        warmup_chunks = int(0.5 * self._rate / self.CHUNK)
        for _ in range(warmup_chunks):
            stream.read(self.CHUNK, exception_on_overflow=False)

        log.info("Waiting for speech…")

        frames: list[bytes] = []
        silent_chunks = 0
        speaking = False
        silence_limit = int(self._silence_dur * self._rate / self.CHUNK)
        # Require at least 0.8s of speech before we accept a recording
        min_speech_chunks = int(0.8 * self._rate / self.CHUNK)
        speech_chunks = 0

        try:
            while True:
                chunk = stream.read(self.CHUNK, exception_on_overflow=False)
                rms = self._rms(chunk)

                if rms > self._silence_thresh:
                    if not speaking:
                        speaking = True
                        if on_start:
                            on_start()
                        log.info("Recording…")
                    silent_chunks = 0
                    speech_chunks += 1
                    frames.append(chunk)
                elif speaking:
                    frames.append(chunk)
                    silent_chunks += 1
                    if silent_chunks >= silence_limit and speech_chunks >= min_speech_chunks:
                        break
                    elif silent_chunks >= silence_limit * 3:
                        # Hard stop: too long without speech
                        break
        finally:
            stream.stop_stream()
            stream.close()

        if not frames:
            return None

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(self._rate)
            wf.writeframes(b"".join(frames))
        return buf.getvalue()


class Transcriber:
    """Whisper-based speech-to-text."""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()
        if _WHISPER_AVAILABLE:
            log.info(f"Loading Whisper ({cfg.whisper_model})…")
            self._model = _whisper.load_model(cfg.whisper_model)
            log.info("Whisper ready.")

    @property
    def available(self) -> bool:
        return self._model is not None

    def transcribe(self, audio_bytes: bytes) -> str | None:
        if self._model is None:
            return None
        tmp = Path("/tmp/jarvis_audio.wav")
        tmp.write_bytes(audio_bytes)
        with self._lock:
            result = self._model.transcribe(
                str(tmp),
                language=cfg.whisper_language,
                fp16=False,
            )
        text = result.get("text", "").strip()
        log.info(f"Transcribed: {text!r}")
        return text or None

    def transcribe_file(self, path: str) -> dict:
        """Transcribe a file by path — thread-safe, for wake word listener."""
        if self._model is None:
            return {"text": ""}
        with self._lock:
            return self._model.transcribe(path, language="en", fp16=False)
