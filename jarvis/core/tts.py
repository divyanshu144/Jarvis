"""
Text-to-speech:
  Primary: ElevenLabs streaming API (sentence-level pipeline)
  Local fallback: Kokoro/Piper command-line TTS when installed/configured
  Final fallback: macOS `say` command
"""

from __future__ import annotations

import queue
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from jarvis.core.config import cfg
from jarvis.core.logger import get_logger

log = get_logger(__name__)

_EL_AVAILABLE = False

try:
    from elevenlabs.client import ElevenLabs as _ELClient
    from elevenlabs.types import VoiceSettings
    _EL_AVAILABLE = True
except ImportError:
    log.warning("elevenlabs package not installed — using macOS say.")


_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z"])')


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _speak_macos(text: str) -> None:
    subprocess.run(["say", "-r", "175", text], check=False)




def _play_file(path: Path) -> None:
    subprocess.run(["afplay", str(path)], check=False)


def _speak_piper(text: str) -> None:
    command = cfg.piper_command
    if not shutil.which(command):
        raise RuntimeError(f"Piper command not found: {command}")
    model_path = cfg.piper_model_path
    if not model_path:
        raise RuntimeError("PIPER_MODEL_PATH or tts.piper_model_path is required for Piper.")
    model = Path(model_path).expanduser()
    if not model.exists():
        raise RuntimeError(f"Piper model not found: {model}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out = Path(f.name)
    try:
        result = subprocess.run(
            [command, "--model", str(model), "--output_file", str(out)],
            input=text,
            text=True,
            capture_output=True,
            timeout=45,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Piper failed")
        _play_file(out)
    finally:
        out.unlink(missing_ok=True)


def _speak_kokoro(text: str) -> None:
    candidates = [cfg.kokoro_command]
    if cfg.kokoro_command == "kokoro":
        candidates.append("kokoro-tts")
    command = next((cmd for cmd in candidates if shutil.which(cmd)), "")
    if not command:
        raise RuntimeError(f"Kokoro command not found: {', '.join(candidates)}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out = Path(f.name)
    try:
        attempts = [
            [command, "--text", text, "--output", str(out)],
            [command, "--text", text, "--output_file", str(out)],
            [command, text, str(out)],
        ]
        last_error = ""
        for args in attempts:
            result = subprocess.run(args, capture_output=True, text=True, timeout=45)
            if result.returncode == 0 and out.exists() and out.stat().st_size > 0:
                _play_file(out)
                return
            last_error = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(last_error or "Kokoro failed")
    finally:
        out.unlink(missing_ok=True)


def _speak_local(text: str, provider: str | None = None) -> None:
    provider = provider or cfg.local_tts_provider
    errors: list[str] = []
    if provider in {"auto", "kokoro"}:
        try:
            log.info("TTS via local Kokoro")
            _speak_kokoro(text)
            return
        except Exception as e:
            errors.append(f"Kokoro: {e}")
            if provider == "kokoro":
                raise
    if provider in {"auto", "piper"}:
        try:
            log.info("TTS via local Piper")
            _speak_piper(text)
            return
        except Exception as e:
            errors.append(f"Piper: {e}")
            if provider == "piper":
                raise
    raise RuntimeError("; ".join(errors) or f"Unknown local TTS provider: {provider}")


def _make_client():
    return _ELClient(api_key=cfg.elevenlabs_key)


def _tts_bytes(client, text: str) -> bytes:
    chunks = client.text_to_speech.stream(
        voice_id=cfg.el_voice_id,
        text=text,
        model_id=cfg.el_model_id,
        voice_settings=VoiceSettings(
            stability=cfg.el_stability,
            similarity_boost=cfg.el_similarity,
        ),
        output_format="mp3_44100_128",
    )
    return b"".join(chunks)


def _play_bytes(audio: bytes) -> None:
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp = Path(f.name)
        f.write(audio)
    _play_file(tmp)
    tmp.unlink(missing_ok=True)


def _speak_elevenlabs_streaming(text: str) -> None:
    """Sentence-level streaming: plays sentence 1 while generating sentence 2+."""
    sentences = _split_sentences(text)
    if not sentences:
        return

    client = _make_client()
    audio_q: queue.Queue[bytes | Exception | None] = queue.Queue(maxsize=3)

    def generate():
        first_error: Exception | None = None
        for s in sentences:
            try:
                audio = _tts_bytes(client, s)
                audio_q.put(audio)
            except Exception as e:
                log.warning(f"TTS sentence failed: {e}")
                if first_error is None:
                    first_error = e
        audio_q.put(first_error)
        audio_q.put(None)

    threading.Thread(target=generate, daemon=True).start()

    played = 0
    first_error: Exception | None = None
    while True:
        item = audio_q.get()
        if item is None:
            break
        if isinstance(item, Exception):
            first_error = item
            continue
        played += 1
        _play_bytes(item)

    if played == 0 and first_error is not None:
        raise first_error


def _speak_elevenlabs(text: str) -> None:
    """Sentence-level streaming: plays sentence 1 while generating sentence 2+.
    Always uses afplay — no mpv dependency required.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return
    if len(sentences) == 1:
        _play_bytes(_tts_bytes(_make_client(), sentences[0]))
    else:
        _speak_elevenlabs_streaming(text)


def speak(text: str) -> None:
    """Speak text aloud. Uses ElevenLabs if configured, otherwise macOS say."""
    if not text.strip():
        return
    clean = (
        text.replace("**", "")
            .replace("*", "")
            .replace("`", "")
            .replace("#", "")
    )
    provider = cfg.tts_provider
    if provider in {"auto", "elevenlabs"} and _EL_AVAILABLE and cfg.elevenlabs_key:
        try:
            log.info("TTS via ElevenLabs (streaming)")
            _speak_elevenlabs(clean)
            return
        except Exception as e:
            log.warning(f"ElevenLabs TTS failed, trying local TTS: {e}")
            if provider == "elevenlabs":
                raise

    if provider in {"auto", "local", "kokoro", "piper"}:
        try:
            local_provider = provider if provider in {"kokoro", "piper"} else None
            _speak_local(clean, local_provider)
            return
        except Exception as e:
            log.warning(f"Local TTS unavailable, falling back to say: {e}")
            if provider in {"local", "kokoro", "piper"}:
                raise

    log.info("TTS via macOS say")
    _speak_macos(clean)
