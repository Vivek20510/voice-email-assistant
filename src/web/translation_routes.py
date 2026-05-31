from flask import Blueprint, jsonify, request, session
import logging

from src.services.preferences import (
    DEFAULT_LANGUAGE,
    get_preferred_language,
    normalize_language,
    set_preferred_language,
)
from src.services.translation import (
    translate_text,
    get_translation_engine,
)

logger = logging.getLogger(__name__)

translation_bp = Blueprint("translation", __name__)

def selected_language() -> str:
    """Return the current user's persisted language or anonymous session choice."""

    user_id = session.get("user_id")
    if user_id:
        return get_preferred_language(user_id)
    return session.get("preferred_language", DEFAULT_LANGUAGE)


# --------------------------------------------------
# SET LANGUAGE
# --------------------------------------------------

@translation_bp.route("/api/set-language", methods=["POST"])
def set_language():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"success": False, "error": "Valid JSON object required."}), 400

        language = normalize_language(data.get("language"))
        user_id = session.get("user_id")

        if user_id:
            set_preferred_language(user_id, language)
        else:
            session["preferred_language"] = language

        return jsonify(
            {
                "success": True,
                "message": "Language updated successfully",
                "language": language,
            }
        )

    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception(
            "Set language failed: %s",
            exc,
        )

        return (
            jsonify(
                {
                    "success": False,
                    "error": str(exc),
                }
            ),
            500,
        )


@translation_bp.route("/api/language-preference", methods=["GET"])
def language_preference():
    return jsonify({"success": True, "language": selected_language()})


# --------------------------------------------------
# TRANSLATE
# --------------------------------------------------

@translation_bp.route("/api/translate", methods=["POST"])
def translate():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"success": False, "error": "Valid JSON object required."}), 400

        text = data.get("text", "")
        if not isinstance(text, str):
            return jsonify({"success": False, "error": "text must be a string."}), 400
        text = text.strip()

        language = data.get("language")

        if not language:
            language = selected_language()
        else:
            language = normalize_language(language)

        if not text:
            return jsonify(
                {
                    "success": True,
                    "translated_text": "",
                    "target_language": language,
                }
            )

        translated_text = translate_text(
            text,
            language,
        )

        return jsonify(
            {
                "success": True,
                "translated_text": translated_text,
                "target_language": language,
                "engine": get_translation_engine(),
                "input_length": len(text),
                "output_length": len(translated_text),
            }
        )

    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception(
            "Translation API Error: %s",
            exc,
        )

        return (
            jsonify(
                {
                    "success": False,
                    "error": "Translation failed",
                    "details": str(exc),
                }
            ),
            500,
        )
