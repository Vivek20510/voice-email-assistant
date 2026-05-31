"""
voice_routes.py

Flask blueprint for Speech-to-Text endpoint.
POST /api/voice/transcribe
"""

from __future__ import annotations

import logging
import os
import tempfile

from flask import Blueprint, jsonify, request

from src.services.voice import transcribe_audio

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
