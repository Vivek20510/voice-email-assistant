from flask import Blueprint, request, jsonify, session
from sqlalchemy import or_

from src.models import EmailMessage
from src.services.nlp_service import summarize_text, suggest_replies

nlp_bp = Blueprint("nlp", __name__, url_prefix="/nlp")
api_nlp_bp = Blueprint("api_nlp", __name__, url_prefix="/api")


def _json_error(message: str, code: int):
    return jsonify({"error": message, "code": code}), code


def _require_login():
    if not session.get("user_id"):
        return _json_error("Unauthorized.", 401)
    return None


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


@api_nlp_bp.route("/ai/search", methods=["POST"])
def search_messages():
    auth_error = _require_login()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    query_text = (payload.get("query") or payload.get("text") or "").strip()
    if not query_text:
        return _json_error("Query is required.", 400)

    pattern = f"%{query_text}%"
    user_id = session.get("user_id")
    matches = (
        EmailMessage.query.filter_by(user_id=user_id)
        .filter(
            or_(
                EmailMessage.subject.ilike(pattern),
                EmailMessage.body.ilike(pattern),
                EmailMessage.to.ilike(pattern),
            )
        )
        .order_by(EmailMessage.created_at.desc(), EmailMessage.id.desc())
        .limit(8)
        .all()
    )

    results = [
        {
            "id": message.id,
            "title": message.subject or "(No subject)",
            "snippet": (
                (message.body or "").strip()[:160] or "No preview available yet."
            ),
            "sender": message.to or session.get("user_email") or "Unknown sender",
            "timestamp": message.created_at.isoformat() if message.created_at else None,
            "channel": "gmail",
        }
        for message in matches
    ]

    return jsonify({"type": "results", "query": query_text, "results": results})
