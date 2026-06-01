"""
voice_routes.py

Flask blueprint for Speech-to-Text endpoint.
POST /api/voice/transcribe
POST /api/voice/tts
"""

from __future__ import annotations

import logging
import os
import tempfile

from flask import Blueprint, Response, jsonify, request

from src.services.preferences import normalize_language
from src.services.translation import translate_text
from src.services.tts import (
    TTSUnavailableError,
    UnsupportedTTSLanguageError,
    synthesize_speech,
)
from src.services.voice import transcribe_audio
from src.web.ai_guard import require_ai_data_usage_enabled

logger = logging.getLogger(__name__)

voice_bp = Blueprint("voice", __name__, url_prefix="/api/voice")

ALLOWED_MIME_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "application/octet-stream",   # some browsers send this for webm
}

MAX_AUDIO_BYTES = 10 * 1024 * 1024   # 10 MB hard limit
MAX_TTS_TEXT_CHARS = int(os.getenv("TTS_MAX_TEXT_CHARS", "4000"))


@voice_bp.route("/tts", methods=["POST"])
def text_to_speech():
    """Synthesize text with local MMS TTS, then fall back to hosted inference."""

    disabled_response = require_ai_data_usage_enabled()
    if disabled_response:
        return disabled_response

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "Valid JSON object required."}), 400

    text = payload.get("text")
    if not isinstance(text, str):
        return jsonify({"success": False, "error": "text must be a string."}), 400
    text = text.strip()
    if not text:
        return jsonify({"success": False, "error": "Text is required."}), 400
    if len(text) > MAX_TTS_TEXT_CHARS:
        return jsonify(
            {
                "success": False,
                "error": f"Text is too long (max {MAX_TTS_TEXT_CHARS} characters).",
            }
        ), 400

    translate = payload.get("translate", False)
    if not isinstance(translate, bool):
        return jsonify({"success": False, "error": "translate must be a boolean."}), 400

    try:
        language = normalize_language(payload.get("language"))
        spoken_text = translate_text(text, language) if translate else text
        result = synthesize_speech(spoken_text, language)
    except (ValueError, UnsupportedTTSLanguageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except TTSUnavailableError as exc:
        logger.warning("TTS unavailable: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 503
    except Exception as exc:
        logger.exception("Unexpected error during speech synthesis: %s", exc)
        return jsonify({"success": False, "error": "Internal speech synthesis error."}), 500

    extension = {
        "audio/flac": "flac",
        "audio/mpeg": "mp3",
        "audio/ogg": "ogg",
    }.get(result.content_type, "wav")
    response = Response(result.audio, mimetype=result.content_type)
    response.headers["Content-Disposition"] = (
        f'inline; filename="read-aloud.{extension}"'
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-TTS-Source"] = result.source
    response.headers["X-TTS-Language"] = result.language
    response.headers["X-TTS-Model"] = result.model_id
    return response


@voice_bp.route("/transcribe", methods=["POST"])
def transcribe():
    """
    Accepts: multipart/form-data with field "audio" (audio blob)
    Returns:
        200 { "success": true,  "transcript": "...", "source": "local"|"hf_api" }
        400 { "success": false, "error": "..." }
        422 { "success": false, "error": "..." }
        503 { "success": false, "error": "..." }
    """

    # --- Validate file field ---
    audio_file = request.files.get("audio")
    if audio_file is None:
        logger.warning("Transcribe request missing 'audio' field.")
        return jsonify({"success": False, "error": "No audio file provided."}), 400

    # --- MIME type check (soft — browsers are inconsistent) ---
    mime = (audio_file.mimetype or "").lower()
    if mime and mime not in ALLOWED_MIME_TYPES:
        logger.warning("Unexpected audio MIME type: %s", mime)
        # Don't hard-reject — warn and continue

    # --- Size check ---
    audio_bytes = audio_file.read()
    if len(audio_bytes) == 0:
        return jsonify({"success": False, "error": "Audio file is empty."}), 400
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        return jsonify({"success": False, "error": "Audio file too large (max 10 MB)."}), 400

    logger.info(
        "Received audio blob: %d bytes, mime=%s",
        len(audio_bytes), mime or "unknown",
    )

    # --- Save to temp file and transcribe ---
    suffix = ".webm" if "webm" in mime else ".wav"
    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix
        ) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        result = transcribe_audio(tmp_path)

    except Exception as exc:
        logger.exception("Unexpected error during transcription: %s", exc)
        return jsonify({"success": False, "error": "Internal transcription error."}), 500

    finally:
        # Always clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass   # non-fatal

    # --- Return result ---
    if result["success"]:
        return jsonify({
            "success":    True,
            "transcript": result["text"],
            "source":     result["source"],
        }), 200
    else:
        error = result.get("error", "Transcription failed.")
        status = 422 if error.startswith("No speech detected.") else 503
        return jsonify({
            "success": False,
            "error":   error,
        }), status
