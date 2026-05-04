from flask import Blueprint, jsonify, request

from src.services.nlp_service import suggest_replies, summarize_text

nlp_bp = Blueprint("nlp", __name__, url_prefix="/nlp")


def _json_error(message: str, code: int):
    return jsonify({"error": message, "code": code}), code


def _text_field(payload: dict, field_name: str) -> str:
    value = payload.get(field_name)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    return value.strip()


@nlp_bp.route("/summarize", methods=["POST"])
def summarize():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _json_error("JSON object payload is required.", 400)

    try:
        text = _text_field(payload, "text")
        subject = _text_field(payload, "subject")
        sender = _text_field(payload, "sender")
        body = _text_field(payload, "body")
    except ValueError as exc:
        return _json_error(str(exc), 400)

    if not any([text, subject, sender, body]):
        return _json_error("Text is required.", 400)

    summary = summarize_text(
        text,
        subject=subject,
        sender=sender,
        body=body,
    )
    return jsonify({"summary": summary})


@nlp_bp.route("/suggest", methods=["POST"])
def suggest():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()

    if not text:
        return _json_error("Text is required.", 400)

    replies = suggest_replies(text)
    return jsonify({"suggestions": replies})
