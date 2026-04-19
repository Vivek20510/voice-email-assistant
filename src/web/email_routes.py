from collections import Counter
from datetime import datetime, timezone

from flask import Blueprint, request, session, jsonify

from src.models import EmailMessage

email_bp = Blueprint("email", __name__, url_prefix="/email")
api_email_bp = Blueprint("api_email", __name__, url_prefix="/api")


def _json_error(message: str, code: int):
    return jsonify({"error": message, "code": code}), code


def _require_login():
    if not session.get("user_id"):
        return _json_error("Unauthorized.", 401)
    return None


def _current_user_id():
    return session.get("user_id")


def _parse_int_arg(name, default, minimum, maximum=None):
    raw_value = request.args.get(name, default)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = default

    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _serialize_message(message, fallback_sender):
    preview = (message.body or "").strip().replace("\r", " ").replace("\n", " ")
    preview = preview[:140] + ("..." if len(preview) > 140 else "")
    folder = "drafts" if message.gmail_id is None else "inbox"
    sender = message.to or fallback_sender or "Unknown sender"
    timestamp = message.created_at or datetime.now(timezone.utc)

    return {
        "id": message.id,
        "sender": sender,
        "subject": message.subject or "(No subject)",
        "preview": preview or "No preview available yet.",
        "timestamp": timestamp.isoformat(),
        "channel": "gmail",
        "is_read": folder == "drafts",
        "folder": folder,
        "label": "draft" if folder == "drafts" else "inbox",
    }


def _query_messages_for_user(user_id, folder, channel, sort, limit, offset):
    query = EmailMessage.query.filter_by(user_id=user_id)

    if channel and channel != "all" and channel != "gmail":
        return []

    if folder == "drafts":
        query = query.filter(EmailMessage.gmail_id.is_(None))
    elif folder == "inbox":
        query = query.filter(EmailMessage.gmail_id.is_not(None))

    if sort == "oldest":
        query = query.order_by(EmailMessage.created_at.asc(), EmailMessage.id.asc())
    else:
        query = query.order_by(EmailMessage.created_at.desc(), EmailMessage.id.desc())

    return query.offset(offset).limit(limit).all()


@email_bp.route("/send", methods=["POST"])
def send_email():
    auth_error = _require_login()
    if auth_error:
        return auth_error

    # stubbed response for Sprint 1
    return jsonify({"status": "queued"})


@email_bp.route("/list", methods=["GET"])
def list_emails():
    auth_error = _require_login()
    if auth_error:
        return auth_error

    return jsonify({"emails": []})


@email_bp.route("/read/<int:message_id>", methods=["GET"])
def read_email(message_id):
    auth_error = _require_login()
    if auth_error:
        return auth_error

    return jsonify({"error": "not implemented", "code": 501}), 501


@api_email_bp.route("/stats", methods=["GET"])
def get_stats():
    auth_error = _require_login()
    if auth_error:
        return auth_error

    user_id = _current_user_id()
    messages = EmailMessage.query.filter_by(user_id=user_id).all()
    now = datetime.now(timezone.utc)
    today = now.date()
    daily_totals = Counter()

    for message in messages:
        created_at = message.created_at or now
        daily_totals[created_at.date().isoformat()] += 1

    trends = []
    for offset in range(6, -1, -1):
        day = today.fromordinal(today.toordinal() - offset)
        trends.append(
            {"date": day.isoformat(), "count": daily_totals.get(day.isoformat(), 0)}
        )

    total_messages = len(messages)
    draft_count = sum(1 for message in messages if message.gmail_id is None)
    unread_count = sum(1 for message in messages if message.gmail_id is not None)
    sent_today = sum(
        1 for message in messages if (message.created_at or now).date() == today
    )
    ai_replies = min(total_messages, max(0, total_messages - draft_count))

    return jsonify(
        {
            "total_messages": total_messages,
            "unread_count": unread_count,
            "sent_today": sent_today,
            "ai_replies": ai_replies,
            "draft_count": draft_count,
            "trends": trends,
        }
    )


@api_email_bp.route("/messages", methods=["GET"])
def get_messages():
    auth_error = _require_login()
    if auth_error:
        return auth_error

    user_id = _current_user_id()
    folder = (request.args.get("folder") or "inbox").strip().lower()
    channel = (request.args.get("channel") or "gmail").strip().lower()
    label = (request.args.get("label") or "").strip().lower()
    sort = (request.args.get("sort") or "newest").strip().lower()
    limit = _parse_int_arg("limit", 20, 1, 100)
    offset = _parse_int_arg("offset", 0, 0)

    messages = _query_messages_for_user(user_id, folder, channel, sort, limit, offset)
    items = [
        _serialize_message(message, session.get("user_email")) for message in messages
    ]

    if label:
        items = [item for item in items if item["label"] == label]

    return jsonify(
        {
            "messages": items,
            "meta": {
                "folder": folder,
                "channel": channel,
                "label": label or None,
                "sort": sort,
                "limit": limit,
                "offset": offset,
                "count": len(items),
            },
        }
    )
