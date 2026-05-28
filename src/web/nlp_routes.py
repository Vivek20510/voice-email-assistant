from flask import Blueprint, jsonify, request

from src.services.ai_service import MODEL_MODE, generate_response
from src.services.nlp_service import summarize_text, suggest_replies
from src.web.ai_panel_routes import ai_query as ai_panel_query
from src.web.compose_routes import compose_draft as compose_draft_handler

nlp_bp = Blueprint("nlp", __name__, url_prefix="/nlp")


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


@nlp_bp.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "success": True,
            "ai_mode": MODEL_MODE,
            "service": "NLP Service Running",
            "ai_engine": "Qwen (ai_service)",
        }
    )


@nlp_bp.route("/summarize", methods=["POST"])
def summarize():
    payload = request.get_json(silent=True)
    if payload is None:
        return _json_error("Valid JSON payload required.")
    if not isinstance(payload, dict):
        return _json_error("JSON object payload is required.")

    try:
        text = _clean_text(payload.get("text"), "text")
        subject = _clean_text(payload.get("subject"), "subject")
        sender = _clean_text(payload.get("sender"), "sender")
        body = _clean_text(payload.get("body"), "body")
    except ValueError as exc:
        return _json_error(str(exc))

    if not (text or subject or sender or body):
        return _json_error("Text is required.")

    try:
        summary = summarize_text(
            text,
            subject=subject,
            sender=sender,
            body=body,
        )
        return jsonify({"success": True, "ai_mode": MODEL_MODE, "summary": summary})
    except Exception as exc:
        print("Summarization Error:", str(exc))
        return _json_error("Failed to summarize email.", 500)


@nlp_bp.route("/suggest", methods=["POST"])
def suggest():
    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return _json_error("Valid JSON payload required.")

    try:
        text = _clean_text(payload.get("text"))
    except ValueError as exc:
        return _json_error(str(exc))

    if not text:
        return _json_error("Text is required.")

    try:
        replies = suggest_replies(text)
        return jsonify({"success": True, "ai_mode": MODEL_MODE, "suggestions": replies})
    except Exception as exc:
        print("Suggestion Error:", str(exc))
        return _json_error("Failed to generate reply suggestions.", 500)


@nlp_bp.route("/assistant", methods=["POST"])
def assistant():
    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return _json_error("Valid JSON payload required.")

    try:
        query = _clean_text(payload.get("query"))
    except ValueError as exc:
        return _json_error(str(exc))

    if not query:
        return _json_error("Query is required.")

    try:
        response = generate_response(query)
        return jsonify(
            {
                "success": True,
                "ai_mode": MODEL_MODE,
                "query": query,
                "response": response,
            }
        )
    except Exception as exc:
        print("Assistant Error:", str(exc))
        return _json_error("Assistant request failed.", 500)


@nlp_bp.route("/ai-query", methods=["POST"])
def ai_query():
    """Temporary compatibility wrapper for /api/ai-panel/query."""
    return ai_panel_query()


@nlp_bp.route("/ai-draft", methods=["POST"])
def ai_draft():
    """Temporary compatibility wrapper for /api/compose/draft."""
    return compose_draft_handler()
