from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from src.db import db
from src.models import User
from src.services.auth import (
    get_auth_url,
    handle_callback,
    hash_password,
    verify_password,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form


def _json_error(message: str, code: int):
    return jsonify({"error": message, "code": code}), code


@auth_bp.route("/login", methods=["GET"])
def login_form():
    return render_template("login.html")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = _request_data()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        if request.is_json:
            return _json_error("Email and password are required.", 400)

        return render_template("login.html", error="Please enter email and password.")

    user = User.query.filter_by(email=email).first()
    if user is None or not verify_password(password, user.password_hash):
        if request.is_json:
            return _json_error("Invalid credentials.", 401)

        return render_template(
            "login.html", error="Incorrect email or password. Please try again."
        )

    session["user_id"] = user.id
    session["user_email"] = user.email
    session.pop("user_name", None)
    session.pop("oauth_state", None)

    if request.is_json:
        return jsonify({"message": "Login successful.", "email": user.email})

    return redirect(url_for("auth.dashboard"))


@auth_bp.route("/google", methods=["GET"])
def google_login():
    auth_url, state = get_auth_url()
    session["oauth_state"] = state
    return redirect(auth_url)


@auth_bp.route("/callback", methods=["GET"])
def oauth_callback():
    try:
        user_info = handle_callback(request.url, session.get("oauth_state"))
    except Exception as exc:
        session.pop("oauth_state", None)
        if request.is_json:
            return _json_error(str(exc), 400)
        return render_template("login.html", error=str(exc)), 400

    email = (user_info.get("email") or "").strip().lower()
    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(user_info.get("sub") or email),
        )
        db.session.add(user)
        db.session.commit()

    session["user_id"] = user.id
    session["user_email"] = user.email
    session["user_name"] = user_info.get("name")
    session.pop("oauth_state", None)
    return redirect(url_for("auth.dashboard"))


@auth_bp.route("/signup", methods=["GET"])
def signup_form():
    return render_template("signup.html")


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = _request_data()

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        if request.is_json:
            return _json_error("Email and password are required.", 400)

        return render_template("signup.html", error="Please enter email and password.")

    existing = User.query.filter_by(email=email).first()
    if existing:
        if request.is_json:
            return _json_error("Email address already registered.", 409)

        return render_template(
            "signup.html",
            error="This email is already registered. Please login instead.",
        )

    user = User(email=email, password_hash=hash_password(password))
    db.session.add(user)
    db.session.commit()

    session["user_id"] = user.id
    session["user_email"] = user.email
    session.pop("user_name", None)
    session.pop("oauth_state", None)

    if request.is_json:
        return jsonify({"message": "Signup successful.", "email": user.email})

    return redirect(url_for("auth.dashboard"))


@auth_bp.route("/logout", methods=["GET"])
def logout():
    session.pop("user_id", None)
    session.pop("user_email", None)
    session.pop("user_name", None)
    session.pop("oauth_state", None)

    if request.is_json:
        return jsonify({"message": "Logged out."}), 200

    return redirect(url_for("auth.login_form"))


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
    if not session.get("user_id"):
        return redirect(url_for("auth.login_form"))
    return render_template("dashboard.html", email=session.get("user_email"))


@auth_bp.route("/settings", methods=["GET"])
def settings():
    if not session.get("user_id"):
        return redirect(url_for("auth.login_form"))

    return render_template("settings.html", email=session.get("user_email"))


@auth_bp.route("/compose", methods=["GET"])
def compose():
    if not session.get("user_id"):
        return redirect(url_for("auth.login_form"))

    return render_template("compose.html", email=session.get("user_email"))
