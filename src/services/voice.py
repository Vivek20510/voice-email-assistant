"""
voice_service.py

Unified Speech-to-Text Service
Merged from voice.py + whisper_service.py

Fallback Chain:
  Local Whisper → HF Whisper API → Error Fallback
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

WHISPER_MODEL_SIZE    = os.getenv("WHISPER_MODEL_SIZE", "tiny.en")
WHISPER_LOCAL_PATH    = os.getenv("WHISPER_LOCAL_PATH")
HF_TOKEN              = os.getenv("HF_TOKEN")
HF_WHISPER_MODEL      = os.getenv("HF_WHISPER_MODEL", "openai/whisper-small")

LOCAL_TIMEOUT_SECONDS = 120
HF_TIMEOUT_SECONDS    = 15

# Whisper no-speech probability — if above this, treat as silence
# Range 0.0–1.0. 0.6 means "60% confident there is no speech → reject"
NO_SPEECH_THRESHOLD   = 0.6

STT_MODE = "error"

# --------------------------------------------------
# GLOBALS
# --------------------------------------------------

_local_attempted: bool    = False
_hf_attempted:    bool    = False
_whisper_model:   Any     = None
_hf_client:       Any     = None

# --------------------------------------------------
# AUDIO CONVERSION: webm/any → 16kHz mono WAV
# --------------------------------------------------

def _ffmpeg_executable() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def _convert_to_wav(input_path: str) -> str | None:
    """
    Convert audio to 16kHz mono WAV using ffmpeg.
    Returns WAV path on success, None if ffmpeg unavailable or fails.
    Caller must delete the returned file.
    """
    try:
        output_tmp  = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        output_path = output_tmp.name
        output_tmp.close()

        proc = subprocess.run(
            [
                _ffmpeg_executable(), "-y",
                "-i", input_path,
                "-ar", "16000",   # Whisper native sample rate
                "-ac", "1",       # mono
                "-f",  "wav",
                output_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,   # capture stderr for logging
            timeout=30,
        )

        if proc.returncode != 0:
            err = proc.stderr.decode(errors="replace")[-300:]
            logger.warning("ffmpeg failed (rc=%d): %s", proc.returncode, err)
            _safe_remove(output_path)
            return None

        # Sanity: file must be non-empty
        if os.path.getsize(output_path) < 100:
            logger.warning("ffmpeg produced empty WAV.")
            _safe_remove(output_path)
            return None

        logger.debug("ffmpeg → WAV: %s", output_path)
        return output_path

    except FileNotFoundError:
        logger.warning("ffmpeg not found. Install ffmpeg and add it to PATH.")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg timed out.")
        return None
    except Exception as exc:
        logger.warning("ffmpeg error: %s", exc)
        return None


def _safe_remove(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# --------------------------------------------------
# NOISE / HALLUCINATION DETECTION
# --------------------------------------------------

# Known Whisper hallucinations for silence / background noise
_NOISE_PHRASES = {
    ".",
    "...",
    "you",
    "bye",
    "yeah",
    "okay",
    "ok",
    "hmm",
    "uh",
    "um",
    "thank you",
    "thanks",
    "thank you.",
    "thanks.",
    "thanks for watching",
    "to the main",
    "to the main.",
    "i used to do the mail",    # ← your specific hallucination
    "i used to do the mail.",
    "[music]",
    "[applause]",
    "[silence]",
    "[blank_audio]",
    "(silence)",
    "(blank audio)",
    "[ silence ]",
}


def _is_hallucination(text: str, no_speech_prob: float | None = None) -> bool:
    """
    Return True if the output looks like a Whisper hallucination.

    Checks:
      1. no_speech_prob from Whisper segments (most reliable)
      2. Known noise phrase exact match
      3. Too short to be real speech
    """
    if not text or not text.strip():
        return True

    # 1. Whisper's own confidence score
    if no_speech_prob is not None and no_speech_prob > NO_SPEECH_THRESHOLD:
        logger.info(
            "Rejecting transcript (no_speech_prob=%.2f > %.2f): '%s'",
            no_speech_prob, NO_SPEECH_THRESHOLD, text.strip()
        )
        return True

    cleaned = text.strip().lower().rstrip(".!?,;")

    # 2. Exact match against known noise phrases
    if cleaned in _NOISE_PHRASES:
        logger.info("Rejecting known noise phrase: '%s'", text.strip())
        return True

    # 3. Too short — real sentences are at least 3 words / 8 chars
    if len(cleaned) < 8:
        logger.info("Rejecting too-short transcript: '%s'", text.strip())
        return True

    return False


# --------------------------------------------------
# LAYER 1 — LOCAL WHISPER
# --------------------------------------------------

def _load_local_whisper() -> bool:
    global _local_attempted, _whisper_model, STT_MODE

    if _local_attempted:
        return _whisper_model is not None
    _local_attempted = True

    try:
        import whisper  # openai-whisper

        if not callable(getattr(whisper, "load_model", None)):
            raise RuntimeError(
                "The installed 'whisper' module is not openai-whisper. "
                "Install the 'openai-whisper' package."
            )

        _whisper_model = whisper.load_model(
            WHISPER_MODEL_SIZE,
            download_root=WHISPER_LOCAL_PATH or None,
        )
        STT_MODE = "local"
        logger.info("Local Whisper '%s' loaded.", WHISPER_MODEL_SIZE)
        return True

    except ImportError:
        logger.warning("openai-whisper not installed.")
    except Exception as exc:
        logger.warning("Local Whisper load failed: %s", exc)

    _whisper_model = None
    return False


def _run_local(audio_path: str) -> tuple[str, float | None]:
    """
    Transcribe with local Whisper.
    Returns (text, avg_no_speech_prob).
    """
    if _whisper_model is None:
        raise RuntimeError("Local Whisper model not loaded.")

    audio: Any = audio_path
    if audio_path.lower().endswith(".wav"):
        import numpy as np

        with wave.open(audio_path, "rb") as wav:
            if (
                wav.getnchannels() != 1
                or wav.getsampwidth() != 2
                or wav.getframerate() != 16000
            ):
                raise RuntimeError("Whisper WAV input must be 16kHz mono PCM.")
            audio = np.frombuffer(wav.readframes(wav.getnframes()), np.int16)
            audio = audio.astype(np.float32) / 32768.0

    result = _whisper_model.transcribe(
        audio,
        fp16=False,         # CPU — FP32 only, silences the warning
        language="en",      # force English → no Hindi/Marathi hallucinations
        temperature=0.0,    # greedy decoding → deterministic, fewer hallucinations
        no_speech_threshold=NO_SPEECH_THRESHOLD,
        logprob_threshold=-1.0,   # don't suppress on low log-prob alone
        condition_on_previous_text=False,  # no context bleeding
    )

    text = (result.get("text") or "").strip()

    # Extract average no_speech_prob from segments
    segments = result.get("segments") or []
    no_speech_prob: float | None = None
    if segments:
        probs = [s.get("no_speech_prob", 0.0) for s in segments if "no_speech_prob" in s]
        if probs:
            no_speech_prob = sum(probs) / len(probs)

    logger.info(
        "Whisper raw: '%s' | no_speech_prob=%s",
        text, f"{no_speech_prob:.2f}" if no_speech_prob is not None else "n/a"
    )

    return text, no_speech_prob


def _transcribe_local(audio_path: str) -> tuple[str, float | None]:
    """Wrapper that enforces the timeout."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_local, audio_path)
        try:
            return future.result(timeout=LOCAL_TIMEOUT_SECONDS)
        except FutureTimeoutError:
            raise RuntimeError(
                f"Local Whisper timed out after {LOCAL_TIMEOUT_SECONDS}s."
            )


# --------------------------------------------------
# LAYER 2 — HF WHISPER API
# --------------------------------------------------

def _load_hf_api() -> bool:
    global _hf_attempted, _hf_client, STT_MODE

    if _hf_attempted:
        return _hf_client is not None
    _hf_attempted = True

    if not HF_TOKEN or HF_TOKEN == "replace-with-huggingface-token":
        logger.warning("HF_TOKEN not set — HF Whisper API unavailable.")
        return False

    from huggingface_hub import InferenceClient

    _hf_client = InferenceClient(
        model=HF_WHISPER_MODEL,
        provider="hf-inference",
        token=HF_TOKEN,
        timeout=HF_TIMEOUT_SECONDS,
    )
    if STT_MODE != "local":
        STT_MODE = "hf_api"

    logger.info("HF Whisper API ready: %s", HF_WHISPER_MODEL)
    return True


def _transcribe_hf(audio_path: str) -> str:
    if not _hf_client:
        raise RuntimeError("HF Whisper API not initialised.")

    result = _hf_client.automatic_speech_recognition(audio_path)
    text = (result.text or "").strip()
    if not text:
        raise RuntimeError("HF API returned empty transcript.")

    return text


# --------------------------------------------------
# MAIN ENTRY POINT
# --------------------------------------------------

def transcribe_audio(file_path: str, language: str | None = None) -> dict[str, Any]:
    """
    Main STT entry point. Converts audio → WAV, then runs fallback chain.

    Returns:
        {
            "success":  bool,
            "text":     str,
            "language": str,
            "segments": list,
            "source":   str,   # "local" | "hf_api" | "error"
            "error":    str | None
        }
    """

    def _ok(text: str, source: str) -> dict:
        return {
            "success":  True,
            "text":     text,
            "language": language or "en",
            "segments": [],
            "source":   source,
            "error":    None,
        }

    def _fail(error: str) -> dict:
        return {
            "success":  False,
            "text":     "",
            "language": language or "en",
            "segments": [],
            "source":   "error",
            "error":    error,
        }

    # Convert to 16kHz WAV first
    wav_path = _convert_to_wav(file_path)
    transcribe_path = wav_path if wav_path else file_path

    try:
        # ── LAYER 1: Local Whisper ──────────────────────────────────
        if _load_local_whisper():
            try:
                text, no_speech_prob = _transcribe_local(transcribe_path)

                if _is_hallucination(text, no_speech_prob):
                    return _fail(
                        "No speech detected. Please speak clearly and try again."
                    )

                logger.info("STT via local Whisper (%d chars).", len(text))
                return _ok(text, "local")

            except Exception as exc:
                logger.warning("Local Whisper failed: %s. Trying HF API.", exc)

        # ── LAYER 2: HF Whisper API ─────────────────────────────────
        if _load_hf_api():
            try:
                text = _transcribe_hf(transcribe_path)

                if _is_hallucination(text):
                    return _fail(
                        "No speech detected. Please speak clearly and try again."
                    )

                logger.info("STT via HF Whisper API (%d chars).", len(text))
                return _ok(text, "hf_api")

            except Exception as exc:
                logger.warning("HF Whisper API failed: %s.", exc)

        # ── LAYER 3: Error Fallback ─────────────────────────────────
        logger.error("All STT layers failed for %s.", file_path)
        return _fail(
            "Speech recognition is currently unavailable. Please type your query."
        )

    finally:
        _safe_remove(wav_path)
