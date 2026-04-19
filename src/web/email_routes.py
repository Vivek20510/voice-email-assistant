from flask import Blueprint, session, jsonify


email_bp = Blueprint("email", __name__, url_prefix="/email")


def _json_error(message: str, code: int):
    return jsonify({"error": message, "code": code}), code


def _require_login():
    if not session.get("user_id"):
        return _json_error("Unauthorized.", 401)
    return None


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
