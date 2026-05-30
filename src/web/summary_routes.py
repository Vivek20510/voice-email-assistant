from flask import Blueprint, jsonify, request

from src.services.summary_service import SummarizerEngine
from src.web.ai_guard import require_ai_data_usage_enabled

summary_bp = Blueprint("summary", __name__, url_prefix="/ai")

# Option 1: Create a single engine instance and reuse it
engine = SummarizerEngine()


def _json_error(message: str, code: int = 400):
    return jsonify({"success": False, "error": message}), code


def _clean_text(value, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    return value.strip()


def _summary_input(payload: dict) -> str:
    text = _clean_text(payload.get("text"), "text")
    subject = _clean_text(payload.get("subject"), "subject")
    sender = _clean_text(payload.get("sender"), "sender")
    body = _clean_text(payload.get("body"), "body")

    if text:
        return text

    parts = []
    if subject:
        parts.append(f"Subject: {subject}")
    if sender:
        parts.append(f"Sender: {sender}")
    if body:
        parts.append(f"Body: {body}")
    return " ".join(parts)


@summary_bp.route("/summary", methods=["POST"])
def summarize():
    disabled_response = require_ai_data_usage_enabled()
    if disabled_response:
        return disabled_response

    data = request.get_json(silent=True)
    if data is None:
        return _json_error("Valid JSON payload required.")
    if not isinstance(data, dict):
        return _json_error("JSON object payload is required.")

    try:
        text = _summary_input(data)
    except ValueError as exc:
        return _json_error(str(exc))

    if not text:
        return _json_error("Text is required.")

    try:
        summary = engine.generate_summary(text)
        return jsonify(
            {
                "success": True,
                "summary": summary,
                "engine": engine.last_engine_mode,
            }
        )

    except Exception as e:
        # Log the error for debugging
        import logging

        logging.exception("Summarization route failed")
        return _json_error(str(e), 500)
