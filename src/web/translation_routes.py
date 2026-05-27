from flask import Blueprint, request, jsonify

from src.services.translation import translate_text

# ✅ CREATE BLUEPRINT

translation_bp = Blueprint("translation", __name__)


# ✅ SIMPLE IN-MEMORY USER LANGUAGE STORE (optional use)

USER_PREF = {"language": "English"}


# ✅ SET LANGUAGE API (optional – for saving preference)


@translation_bp.route("/api/set-language", methods=["POST"])
def set_language():

    try:

        data = request.get_json(force=True)

        language = data.get("language", "English")

        USER_PREF["language"] = language

        return jsonify(
            {"message": "Language updated successfully", "language": language}
        )

    except Exception as e:

        return jsonify({"error": str(e)}), 500


# ✅ TRANSLATE API (USED BY DASHBOARD.JS)


@translation_bp.route("/api/translate", methods=["POST"])
def translate():

    try:

        # ✅ FIX: removed trailing comma (important!)

        data = request.get_json(force=True)

        # ✅ Extract inputs

        text = data.get("text", "")

        language = data.get("language")

        # ✅ fallback to stored preference if not passed

        if not language:

            language = USER_PREF.get("language", "English")

        # ✅ Basic validation

        if not text:

            return jsonify({"translated_text": ""})

        # ✅ Call translation function

        translated_text = translate_text(text, language)

        # ✅ Return response (frontend expects this exact key)

        return jsonify(
            {"translated_text": translated_text, "target_language": language}
        )

    except Exception as e:

        print("❌ Translation API Error:", str(e))

        return jsonify({"error": "Translation failed", "details": str(e)}), 500
