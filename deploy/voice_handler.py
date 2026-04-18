"""
voice_handler.py — STT + TTS integration for DeepAgents Telegram bot.

Speech-to-text:  faster-whisper (tiny, CPU, ~75 MB, handles .ogg natively)
Text-to-speech:  ElevenLabs API (eleven_turbo_v2 — fastest + cheapest)

Free-tier budget:
  ElevenLabs: ~10,000 chars/month.  We cap at 9,500 (500 safety buffer).
  faster-whisper: fully local — unlimited.

Environment variables (all optional — voice features silently disabled if absent):
  ELEVENLABS_API_KEY    Your ElevenLabs API key
  ELEVEN_LABS_VOICE_ID  Voice ID (required — set in .env or Render env vars)
  ELEVEN_LABS_MODEL     Model ID (default: eleven_turbo_v2)
  DA_VOICE_REPLY        "1" to always reply with audio (default: only when
                        user sent a voice message)
  DA_TTS_MAX_CHARS      Max chars per response to synthesize (default: 400)
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger("deepagents.voice")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_ELEVEN_KEY   = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_LABS_API_KEY", "")
_VOICE_ID     = os.environ.get("ELEVEN_LABS_VOICE_ID") or os.environ.get("ELEVEN_LABS_VOICE", "")
_MODEL_ID     = os.environ.get("ELEVEN_LABS_MODEL", "eleven_turbo_v2")
_MAX_CHARS    = int(os.environ.get("DA_TTS_MAX_CHARS", "400"))
_MONTHLY_CAP  = 9_500   # chars/month — leaves 500 buffer from the 10k free tier
_QUOTA_FILE   = Path.home() / ".deepagents" / "elevenlabs_quota.json"


# ---------------------------------------------------------------------------
# Monthly quota tracker (JSON, survives restarts)
# ---------------------------------------------------------------------------

def _load_quota() -> dict:
    try:
        if _QUOTA_FILE.exists():
            return json.loads(_QUOTA_FILE.read_text())
    except Exception:
        pass
    return {"month": _current_month(), "chars_used": 0}


def _save_quota(data: dict) -> None:
    try:
        _QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
        _QUOTA_FILE.write_text(json.dumps(data))
    except Exception:
        pass


def _current_month() -> str:
    return time.strftime("%Y-%m")


def chars_remaining() -> int:
    """How many ElevenLabs characters are left this month."""
    data = _load_quota()
    if data.get("month") != _current_month():
        return _MONTHLY_CAP  # new month — full budget
    return max(0, _MONTHLY_CAP - data.get("chars_used", 0))


def _track_chars(n: int) -> None:
    data = _load_quota()
    if data.get("month") != _current_month():
        data = {"month": _current_month(), "chars_used": 0}
    data["chars_used"] = data.get("chars_used", 0) + n
    _save_quota(data)


# ---------------------------------------------------------------------------
# Speech-to-text  (faster-whisper)
# ---------------------------------------------------------------------------

_stt_model = None  # lazy-loaded on first voice message


def _get_stt():
    global _stt_model
    if _stt_model is not None:
        return _stt_model
    try:
        from faster_whisper import WhisperModel
        logger.info("Loading faster-whisper tiny model (first voice message)…")
        _stt_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        logger.info("faster-whisper ready")
    except ImportError:
        logger.warning("faster-whisper not installed — pip install faster-whisper")
    return _stt_model


def transcribe(audio_path: str | Path) -> str:
    """Transcribe an audio file (.ogg/.mp3/.wav) to text.

    Returns empty string on failure so the caller can fall back gracefully.
    """
    model = _get_stt()
    if model is None:
        return ""
    try:
        segments, info = model.transcribe(str(audio_path), beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        logger.info("Transcribed (%s, %.1fs): %s", info.language, info.duration, text[:80])
        return text
    except Exception as exc:
        logger.warning("Transcription failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Text-to-speech  (ElevenLabs)
# ---------------------------------------------------------------------------

_eleven_client = None  # lazy-loaded


def _get_eleven():
    global _eleven_client
    if _eleven_client is not None:
        return _eleven_client
    if not _ELEVEN_KEY:
        return None
    try:
        from elevenlabs import ElevenLabs
        _eleven_client = ElevenLabs(api_key=_ELEVEN_KEY)
        logger.info("ElevenLabs client ready (voice=%s, model=%s)", _VOICE_ID, _MODEL_ID)
    except ImportError:
        logger.warning("elevenlabs not installed — pip install elevenlabs")
    return _eleven_client


def synthesize(text: str) -> bytes | None:
    """Convert text to speech MP3 bytes using ElevenLabs.

    Returns None when:
    - ElevenLabs is not configured
    - Text is too long (> DA_TTS_MAX_CHARS) — saves quota for real voice replies
    - Monthly quota would be exceeded
    - Any API error occurs
    """
    client = _get_eleven()
    if client is None:
        return None

    # Trim to max chars (saves quota, keeps responses snappy)
    trimmed = text[:_MAX_CHARS]
    n = len(trimmed)

    if chars_remaining() < n:
        logger.warning(
            "ElevenLabs quota low (%d chars left, need %d) — skipping TTS",
            chars_remaining(), n,
        )
        return None

    try:
        audio = client.text_to_speech.convert(
            text=trimmed,
            voice_id=_VOICE_ID,
            model_id=_MODEL_ID,
            output_format="mp3_22050_32",   # smallest MP3 — fine for voice
        )
        # SDK may return a generator; collect into bytes
        if hasattr(audio, "__iter__") and not isinstance(audio, bytes):
            audio = b"".join(audio)
        _track_chars(n)
        logger.info("TTS synthesized %d chars (%d chars remaining this month)", n, chars_remaining())
        return audio
    except Exception as exc:
        logger.warning("ElevenLabs TTS failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Convenience: is voice enabled?
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# NVIDIA Magpie TTS fallback (free tier via build.nvidia.com, 40 RPM)
# ---------------------------------------------------------------------------

_NVIDIA_KEY   = os.environ.get("NVIDIA_API_KEY", "")
_NVIDIA_TTS_URL   = os.environ.get(
    "NVIDIA_TTS_URL",
    "https://integrate.api.nvidia.com/v1/audio/speech",
)
_NVIDIA_TTS_MODEL = os.environ.get("NVIDIA_TTS_MODEL", "nvidia/magpie-tts-multilingual")
_NVIDIA_TTS_VOICE = os.environ.get("NVIDIA_TTS_VOICE", "Magpie-Multilingual.EN-US.Ray")


def synthesize_nvidia(text: str) -> bytes | None:
    """Synthesize speech via NVIDIA NIM Magpie TTS. Returns MP3 bytes or None."""
    if not _NVIDIA_KEY or not text.strip():
        return None
    trimmed = text[:_MAX_CHARS]
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed — cannot call NVIDIA TTS")
        return None
    payload = {
        "model": _NVIDIA_TTS_MODEL,
        "input": trimmed,
        "voice": _NVIDIA_TTS_VOICE,
        "response_format": "mp3",
    }
    headers = {
        "Authorization": f"Bearer {_NVIDIA_KEY}",
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(_NVIDIA_TTS_URL, json=payload, headers=headers)
        if resp.status_code != 200:
            logger.warning("NVIDIA TTS failed %s: %s", resp.status_code, resp.text[:200])
            return None
        data = resp.content
        if not data or len(data) < 128:
            logger.warning("NVIDIA TTS returned empty/short payload (%d bytes)", len(data or b""))
            return None
        logger.info("NVIDIA TTS synthesized %d chars (%d bytes MP3)", len(trimmed), len(data))
        return data
    except Exception as exc:
        logger.warning("NVIDIA TTS call raised: %s", exc)
        return None


def synthesize_any(text: str) -> tuple[bytes, str] | None:
    """Provider-fallback TTS. Tries ElevenLabs → NVIDIA Magpie.
    Returns (audio_bytes, provider_name) or None if every provider failed.
    The caller may then fall through to browser speechSynthesis."""
    if not text.strip():
        return None
    # Tier 1: ElevenLabs (best quality, quota-limited)
    audio = synthesize(text)
    if audio:
        return audio, "elevenlabs"
    # Tier 2: NVIDIA Magpie (free, 40 RPM)
    audio = synthesize_nvidia(text)
    if audio:
        return audio, "nvidia"
    return None


def tts_available() -> bool:
    """Return True if ElevenLabs is configured and has quota remaining."""
    return bool(_ELEVEN_KEY) and chars_remaining() > 20


def stt_available() -> bool:
    """Return True if faster-whisper can be imported."""
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False
