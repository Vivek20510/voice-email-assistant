from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
)
from src.models import User, UserToken
from src.services.auth import hash_password, verify_password
from src.db import db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form


def _json_error(message: str, code: int):
    return jsonify({"error": message, "code": code}), code


def _user_initials(email: str | None) -> str:
    if not email:
        return "VE"

    local_part = email.split("@", 1)[0]
    cleaned = "".join(ch for ch in local_part if ch.isalnum())
    return (cleaned[:2] or "VE").upper()


def _create_user():
    data = _request_data()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        if request.is_json:
            return _json_error("Email and password are required.", 400)
        return render_template("login.html", error="Please enter email and password.")

    existing = User.query.filter_by(email=email).first()
    if existing:
        if request.is_json:
            return _json_error("Email address already registered.", 409)
        return render_template(
            "login.html",
            error="This email is already registered. Please login instead.",
        )

    user = User(email=email, password_hash=hash_password(password))
    db.session.add(user)
    db.session.commit()

    session["user_id"] = user.id
    session["user_email"] = user.email

    if request.is_json:
        return jsonify({"message": "Signup successful.", "email": user.email})

    return redirect(url_for("auth.dashboard"))


@auth_bp.route("/login", methods=["GET"])
def login_form():
    return render_template("login.html")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = _request_data()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    # Empty fields
    if not email or not password:
        if request.is_json:
            return _json_error("Email and password are required.", 400)

        return render_template("login.html", error="Please enter email and password.")

    user = User.query.filter_by(email=email).first()

    # Invalid Login
    if user is None or not verify_password(password, user.password_hash):

        if request.is_json:
            return _json_error("Invalid credentials.", 401)

        return render_template(
            "login.html", error="Incorrect email or password. Please try again."
        )

    # Success Login
    session["user_id"] = user.id
    session["user_email"] = user.email

    if request.is_json:
        return jsonify({"message": "Login successful.", "email": user.email})

    return redirect(url_for("auth.dashboard"))


@auth_bp.route("/signup", methods=["GET"])
def signup_form():
    return redirect(url_for("auth.login_form", tab="register"))


@auth_bp.route("/signup", methods=["POST"])
def signup():
    return _create_user()


@auth_bp.route("/register", methods=["POST"])
def register():
    return _create_user()


@auth_bp.route("/logout", methods=["GET"])
def logout():
    session.pop("user_id", None)
    session.pop("user_email", None)
    return jsonify({"message": "Logged out."}), 200


@auth_bp.route("/status", methods=["GET"])
def status():
    user_id = session.get("user_id")
    if not user_id:
        return _json_error("Unauthorized.", 401)

    user = db.session.get(User, user_id)
    if not user:
        return _json_error("Unauthorized.", 401)

    return jsonify({"id": user.id, "email": user.email})


@auth_bp.route("/dashboard", methods=["GET"])
def dashboard():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    email = session.get("user_email")
    services = {
        "gmail": False,
        "telegram": False,
    }
    tokens = UserToken.query.filter_by(user_id=user_id).all()
    for token in tokens:
        if token.service in services:
            services[token.service] = True

    return render_template(
        "dashboard.html",
        email=email,
        user_initials=_user_initials(email),
        services=services,
    )


@auth_bp.route("/settings", methods=["GET"])
def settings():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    return render_template("settings.html", email=session.get("user_email"))


@auth_bp.route("/compose", methods=["GET"])
def compose():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    return render_template("compose.html", email=session.get("user_email"))
