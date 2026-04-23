from flask import Blueprint, jsonify, request, session

from src.services.email_service import (
    EmailServiceError,
    list_emails as gmail_list_emails,
    read_email as gmail_read_email,
    send_email as gmail_send_email,
)

email_bp = Blueprint("email", __name__, url_prefix="/email")
messages_bp = Blueprint("messages", __name__, url_prefix="/api")


def _json_error(message: str, code: int):
    return jsonify({"error": message, "code": code}), code


def _require_login():
    if not session.get("user_id"):
        return _json_error("Unauthorized.", 401)
    return None


def _request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form


def _current_user_id():
    return session.get("user_id")


def _parse_limit():
    raw_limit = request.args.get("limit", 10)
    try:
        return max(1, min(int(raw_limit), 50))
    except (TypeError, ValueError):
        raise EmailServiceError("Invalid limit parameter.", 400)


def _serialize_service_error(exc: EmailServiceError):
    return _json_error(exc.message, exc.status_code)


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
    except EmailServiceError as exc:
        return _serialize_service_error(exc)

    return jsonify(result)


@messages_bp.route("/messages", methods=["GET"])
def api_list_messages():
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


@messages_bp.route("/messages/<message_id>", methods=["GET"])
def api_read_message(message_id):
    auth_error = _require_login()
    if auth_error:
        return auth_error

    try:
        result = gmail_read_email(_current_user_id(), message_id)
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
