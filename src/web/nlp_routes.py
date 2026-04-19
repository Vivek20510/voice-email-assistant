from flask import Blueprint, jsonify, request

from src.services.nlp_service import suggest_replies, summarize_text

nlp_bp = Blueprint("nlp", __name__, url_prefix="/nlp")


def _json_error(message: str, code: int):
    return jsonify({"error": message, "code": code}), code


@nlp_bp.route("/summarize", methods=["POST"])
def summarize():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()

    if not text:
        return _json_error("Text is required.", 400)

    summary = summarize_text(text)
    return jsonify({"summary": summary})


@nlp_bp.route("/suggest", methods=["POST"])
def suggest():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()

    if not text:
        return _json_error("Text is required.", 400)

    replies = suggest_replies(text)
    return jsonify({"suggestions": replies})
