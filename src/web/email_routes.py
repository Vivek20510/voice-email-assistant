from flask import Blueprint, jsonify, request, session
import logging

from src.services.email_service import (
    EmailServiceError,
    list_emails as gmail_list_emails,
    read_email as gmail_read_email,
    send_email as gmail_send_email,
)
from src.services.outlook_service import (
    OutlookServiceError,
    list_emails as outlook_list_emails,
    read_email as outlook_read_email,
)

logger = logging.getLogger(__name__)

email_bp = Blueprint("email", __name__, url_prefix="/email")
messages_bp = Blueprint("messages", __name__, url_prefix="/api")


def _json_error(message: str, code: int):
    return jsonify({"error": message, "code": code}), code


def _require_login():
    if not session.get("user_id"):
        logger.debug("Request rejected: not logged in")
        return _json_error("Unauthorized.", 401)
    return None


def _validate_outlook_session():
    """Validate Outlook session state before service calls.

    Returns:
        tuple: (is_valid: bool, error_response: tuple | None)
            If valid, returns (True, None)
            If invalid, returns (False, error_response)

    Checks:
        - User is logged in (session['user_id'] exists)
        - Outlook is enabled (session['outlook_enabled'] is True)
    """
    if not session.get("user_id"):
        logger.debug("Outlook request rejected: not logged in")
        return False, _json_error("Unauthorized.", 401)

    if not session.get("outlook_enabled", False):
        logger.debug(
            f"Outlook request rejected: not enabled for user {session.get('user_id')}"
        )
        return False, _json_error("Outlook not enabled.", 409)

    return True, None


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


def _serialize_outlook_error(exc: OutlookServiceError):
    return _json_error(exc.message, exc.status_code)


def _serialize_error(message: str, code: int):
    return _json_error(message, code)


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


@messages_bp.route("/channels/outlook", methods=["POST"])
def api_toggle_outlook():
    auth_error = _require_login()
    if auth_error:
        return auth_error

    data = _request_data()
    enabled = data.get("enabled", False)

    user_id = session.get("user_id")
    session["outlook_enabled"] = bool(enabled)
    logger.debug(f"User {user_id} toggled Outlook: enabled={bool(enabled)}")

    return jsonify({"outlook_enabled": session["outlook_enabled"]})


@messages_bp.route("/outlook/inbox", methods=["GET"])
def api_list_outlook_emails():
    """List Outlook inbox emails.

    Requires:
        - User logged in (session['user_id'])
        - Outlook enabled (session['outlook_enabled'] = True)

    Query params:
        - limit: Max emails to return (1-100, default 10)
        - sort_by: Sort field ("received_time" or "subject", default "received_time")
        - ascending: Sort order ("true" or "false", default "false")

    Error responses:
        - 401: Not logged in
        - 409: Outlook not enabled
        - 503: Outlook unavailable

    Success response:
        - 200: {"emails": [...], "messages": [...], "next_page_token": null}
    """
    # Session validation (checks login + enabled)
    is_valid, error_response = _validate_outlook_session()
    if not is_valid:
        return error_response

    user_id = session.get("user_id")
    limit = request.args.get("limit", 10, type=int)
    sort_by = request.args.get("sort_by", "received_time")
    ascending = request.args.get("ascending", "false").lower() == "true"

    logger.debug(
        f"List Outlook emails - user {user_id}: limit={limit}, sort_by={sort_by}, ascending={ascending}"
    )

    try:
        result = outlook_list_emails(
            user_id,
            limit=limit,
            sort_by=sort_by,
            ascending=ascending,
        )
        logger.debug(
            f"Successfully listed {len(result.get('emails', []))} Outlook emails"
        )
        return jsonify(result)
    except OutlookServiceError as exc:
        logger.error(
            f"Outlook list error for user {user_id}: {exc.message} (code {exc.status_code})"
        )
        return _serialize_outlook_error(exc)
    except Exception as exc:
        logger.error(f"Unexpected error listing Outlook emails: {exc}", exc_info=True)
        return _json_error("Internal server error.", 500)


@messages_bp.route("/outlook/inbox/<encoded_message_id>", methods=["GET"])
def api_read_outlook_email(encoded_message_id):
    """Read a single Outlook inbox email.

    Requires:
        - User logged in (session['user_id'])
        - Outlook enabled (session['outlook_enabled'] = True)

    Path params:
        - encoded_message_id: Base64-encoded Outlook EntryID

    Error responses:
        - 400: Invalid message ID format
        - 401: Not logged in
        - 404: Message not found
        - 409: Outlook not enabled
        - 503: Outlook unavailable

    Success response:
        - 200: Message details dict
    """
    # Session validation (checks login + enabled)
    is_valid, error_response = _validate_outlook_session()
    if not is_valid:
        return error_response

    user_id = session.get("user_id")
    logger.debug(
        f"Read Outlook email - user {user_id}: message_id={encoded_message_id[:20]}..."
    )

    try:
        result = outlook_read_email(user_id, encoded_message_id)
        logger.debug(f"Successfully read Outlook email for user {user_id}")
        return jsonify(result)
    except OutlookServiceError as exc:
        logger.warning(
            f"Outlook read error for user {user_id}: {exc.message} (code {exc.status_code})"
        )
        return _serialize_outlook_error(exc)
    except Exception as exc:
        logger.error(f"Unexpected error reading Outlook email: {exc}", exc_info=True)
        return _json_error("Internal server error.", 500)
