from flask import Blueprint, jsonify, request, session


from src.db import db

from src.models import ReadMessage

from src.services.email_service import (
    EmailServiceError,
    GmailConnectionError,
    list_emails as gmail_list_emails,
    read_email as gmail_read_email,
    send_email as gmail_send_email,
)

from src.services.outlook_service import (
    OutlookConnectionError,
    list_emails as outlook_list_emails,
    read_email as outlook_read_email,
)

email_bp = Blueprint("email", __name__, url_prefix="/email")

messages_bp = Blueprint("messages", __name__, url_prefix="/api")


def _json_error(message: str, code: int):

    return jsonify({"error": message, "code": code}), code


def _require_login():

    if not session.get("user_id"):

        return _json_error("Unauthorized.", 401)

    return None


def _require_outlook_enabled():
    auth_error = _require_login()
    if auth_error:
        return auth_error
    if not session.get("outlook_enabled"):
        return _json_error("Outlook not enabled.", 409)
    return None


def _request_data():

    if request.is_json:

        return request.get_json(silent=True) or {}

    return request.form


def _current_user_id():

    return session.get("user_id")


def _parse_limit():

    raw_limit = request.args.get("limit", 25)

    try:

        return max(1, min(int(raw_limit), 50))

    except (TypeError, ValueError):

        raise EmailServiceError("Invalid limit parameter.", 400)


def _serialize_service_error(exc: EmailServiceError):

    return _json_error(exc.message, exc.status_code)


def _parse_channel(default: str = "all"):

    return (request.args.get("channel") or default).strip().lower()


def _sort_messages(messages: list[dict]) -> list[dict]:

    def sort_key(message):

        value = message.get("received_at")

        if not value:

            return ""

        return str(value)

    return sorted(messages, key=sort_key, reverse=True)


def _message_channel(message: dict, default: str = "gmail") -> str:

    return (message.get("channel") or default).strip().lower()


def _message_key(message: dict) -> str | None:

    return message.get("id") or message.get("outlook_id") or message.get("gmail_id")


def _read_keys_for_user(user_id: int) -> set[tuple[str, str]]:

    rows = ReadMessage.query.filter_by(user_id=user_id).all()

    return {(row.channel, row.message_id) for row in rows}


def _apply_local_read_state(messages: list[dict], user_id: int) -> list[dict]:

    read_keys = _read_keys_for_user(user_id)

    for message in messages:

        message_id = _message_key(message)

        if message_id and (_message_channel(message), str(message_id)) in read_keys:

            message["unread"] = False

            if isinstance(message.get("labels"), list):

                message["labels"] = [
                    label for label in message["labels"] if label != "UNREAD"
                ]

    return messages


def _mark_local_read(user_id: int, message: dict):

    message_id = _message_key(message)

    if not message_id:

        return

    channel = _message_channel(message)

    existing = ReadMessage.query.filter_by(
        user_id=user_id,
        channel=channel,
        message_id=str(message_id),
    ).first()

    if existing is None:

        db.session.add(
            ReadMessage(user_id=user_id, channel=channel, message_id=str(message_id))
        )

        db.session.commit()

    message["unread"] = False

    if isinstance(message.get("labels"), list):

        message["labels"] = [label for label in message["labels"] if label != "UNREAD"]


def _send_payload_error(data):

    to = (data.get("to") or "").strip()

    body = (data.get("body") or data.get("message") or "").strip()

    subject = (data.get("subject") or "").strip()

    channel = (data.get("channel") or "gmail").strip().lower()

    if channel != "gmail":

        return None, _json_error("Only Gmail sending is supported right now.", 501)

    if not to or not body:

        return None, _json_error("To and body are required.", 400)

    return {"to": to, "subject": subject, "body": body}, None


@email_bp.route("/send", methods=["POST"])
def send_email():

    auth_error = _require_login()

    if auth_error:

        return auth_error

    payload, validation_error = _send_payload_error(_request_data())

    if validation_error:

        return validation_error

    try:

        result = gmail_send_email(_current_user_id(), **payload)

    except EmailServiceError as exc:

        return _serialize_service_error(exc)

    return jsonify(result)


@email_bp.route("/list", methods=["GET"])
def list_emails():

    auth_error = _require_login()

    if auth_error:

        return auth_error

    try:

        result = gmail_list_emails(
            _current_user_id(),
            limit=_parse_limit(),
            page_token=request.args.get("page_token"),
            label_ids=request.args.getlist("label"),
        )

    except EmailServiceError as exc:

        return _serialize_service_error(exc)

    return jsonify(result)


@email_bp.route("/read/<message_id>", methods=["GET"])
def read_email(message_id):

    auth_error = _require_login()

    if auth_error:

        return auth_error

    try:

        result = gmail_read_email(_current_user_id(), message_id)

        _mark_local_read(_current_user_id(), result)

    except EmailServiceError as exc:

        return _serialize_service_error(exc)

    return jsonify(result)


@messages_bp.route("/messages", methods=["GET"])
def api_list_messages():

    auth_error = _require_login()

    if auth_error:

        return auth_error

    limit = _parse_limit()

    channel = _parse_channel()

    try:

        if channel == "gmail":

            result = gmail_list_emails(
                _current_user_id(),
                limit=limit,
                page_token=request.args.get("page_token"),
                label_ids=request.args.getlist("label"),
            )

            messages = result.get("messages") or result.get("emails") or []

            _apply_local_read_state(messages, _current_user_id())

            result["messages"] = messages

            result["emails"] = messages

            return jsonify(result)

        if channel == "outlook":

            result = outlook_list_emails(_current_user_id(), limit=limit)

            messages = result.get("messages") or result.get("emails") or []

            _apply_local_read_state(messages, _current_user_id())

            result["messages"] = messages

            result["emails"] = messages

            return jsonify(result)

        if channel not in {"all", "inbox"}:

            return _json_error("Unsupported message channel.", 400)

        messages = []

        connection_errors = []

        try:

            gmail_result = gmail_list_emails(
                _current_user_id(),
                limit=limit,
                page_token=request.args.get("page_token"),
                label_ids=request.args.getlist("label"),
            )

            messages.extend(
                gmail_result.get("messages") or gmail_result.get("emails") or []
            )

        except GmailConnectionError as exc:

            connection_errors.append(exc)

        try:

            outlook_result = outlook_list_emails(_current_user_id(), limit=limit)

            messages.extend(
                outlook_result.get("messages") or outlook_result.get("emails") or []
            )

        except OutlookConnectionError as exc:

            connection_errors.append(exc)

        if not messages and len(connection_errors) == 2:

            return _json_error(
                "Connect Gmail or Outlook to load your inbox.",
                409,
            )

        sorted_messages = _apply_local_read_state(
            _sort_messages(messages)[:limit],
            _current_user_id(),
        )

        result = {
            "emails": sorted_messages,
            "messages": sorted_messages,
            "next_page_token": None,
        }

    except EmailServiceError as exc:

        return _serialize_service_error(exc)

    return jsonify(result)


@messages_bp.route("/messages/<message_id>", methods=["GET"])
def api_read_message(message_id):

    auth_error = _require_login()

    if auth_error:

        return auth_error

    try:

        if message_id.startswith("outlook:"):

            result = outlook_read_email(_current_user_id(), message_id)

        else:

            result = gmail_read_email(_current_user_id(), message_id)

        _mark_local_read(_current_user_id(), result)

    except EmailServiceError as exc:

        return _serialize_service_error(exc)

    return jsonify(result)


@messages_bp.route("/send", methods=["POST"])
def api_send_message():

    auth_error = _require_login()

    if auth_error:

        return auth_error

    payload, validation_error = _send_payload_error(_request_data())

    if validation_error:

        return validation_error

    try:

        result = gmail_send_email(_current_user_id(), **payload)

    except EmailServiceError as exc:

        return _serialize_service_error(exc)

    return jsonify(result)


@messages_bp.route("/outlook/inbox", methods=["GET"])
def api_outlook_inbox():
    enabled_error = _require_outlook_enabled()
    if enabled_error:
        return enabled_error

    try:
        result = outlook_list_emails(_current_user_id(), limit=_parse_limit())
    except EmailServiceError as exc:
        return _serialize_service_error(exc)

    return jsonify(result)


@messages_bp.route("/outlook/inbox/<message_id>", methods=["GET"])
def api_outlook_message(message_id):
    enabled_error = _require_outlook_enabled()
    if enabled_error:
        return enabled_error

    try:
        result = outlook_read_email(_current_user_id(), message_id)
        _mark_local_read(_current_user_id(), result)
    except EmailServiceError as exc:
        return _serialize_service_error(exc)

    return jsonify(result)
