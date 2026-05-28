from flask import Blueprint, jsonify, request

from src.services import qwen_draft_service

compose_bp = Blueprint("compose_api", __name__, url_prefix="/api/compose")


def _json_error(message: str, code: int = 400):
    return jsonify({"success": False, "error": message, "code": code}), code


def _clean_text(value, field_name: str | None = None):
    if value is None:
        return ""
    if not isinstance(value, str):
        if field_name:
            raise ValueError(f"{field_name} must be a string.")
        raise ValueError("All fields must be strings.")
    return value.strip()


@compose_bp.route("/draft", methods=["POST"])
def compose_draft():
    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return _json_error("Valid JSON payload required.")

    try:
        email_text = _clean_text(
            payload.get("text") or payload.get("prompt") or payload.get("subject"),
            "text",
        )
        tone = _clean_text(payload.get("tone") or "professional", "tone").lower()
        if tone not in {"casual", "formal", "professional"}:
            tone = "professional"
    except ValueError as exc:
        return _json_error(str(exc))

    if not email_text:
        return _json_error("Email text is required.")

    try:
        drafts = qwen_draft_service.generate_qwen_drafts(email_text, tones=[tone])
        draft = drafts.get(tone) or drafts.get("professional") or next(
            iter(drafts.values()),
            "",
        )

        return jsonify(
            {
                "success": True,
                "ai_mode": qwen_draft_service.get_draft_model_mode(),
                "tone": tone,
                "draft": draft,
                "drafts": drafts,
            }
        )
    except Exception as exc:
        print("AI Draft Error:", str(exc))
        return _json_error("AI draft generation failed.", 500)
