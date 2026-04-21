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
from src.models import User, UserToken
from src.services.auth import (
    compute_expiry,
    get_auth_url,
    get_gmail_auth_url,
    handle_callback,
    handle_gmail_callback,
    hash_password,
    verify_password,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
channel_bp = Blueprint("channels", __name__, url_prefix="/api/channels")


def _request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form


def _json_error(message: str, code: int):
    return jsonify({"error": message, "code": code}), code


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def _gmail_token_for_user(user_id: int | None):
    if not user_id:
        return None
    return UserToken.query.filter_by(user_id=user_id, service="gmail").first()


def _settings_context(**extra):
    gmail_token = _gmail_token_for_user(session.get("user_id"))
    context = {
        "email": session.get("user_email"),
        "gmail_connected": gmail_token is not None,
        "gmail_email": gmail_token.account_email if gmail_token else None,
        "gmail_error": session.pop("gmail_error", None),
        "gmail_success": session.pop("gmail_success", None),
    }
    context.update(extra)
    return context


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


@auth_bp.route("/gmail/connect", methods=["GET"])
def gmail_connect():
    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login_form"))

    auth_url, state = get_gmail_auth_url()
    next_target = request.args.get("next") or "settings"
    session["gmail_oauth_state"] = state
    session["gmail_oauth_next"] = next_target
    return redirect(auth_url)


@auth_bp.route("/gmail/callback", methods=["GET"])
def gmail_callback():
    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login_form"))

    next_target = session.get("gmail_oauth_next") or "settings"

    try:
        oauth_data = handle_gmail_callback(
            request.url, session.get("gmail_oauth_state")
        )
    except Exception as exc:
        session.pop("gmail_oauth_state", None)
        session.pop("gmail_oauth_next", None)
        session["gmail_error"] = str(exc)
        return redirect(url_for("auth.settings"))

    user_info = oauth_data["user_info"]
    gmail_token = _gmail_token_for_user(user.id)
    if gmail_token is None:
        gmail_token = UserToken(user_id=user.id, service="gmail")
        db.session.add(gmail_token)

    gmail_token.account_email = (user_info.get("email") or "").strip().lower() or None
    gmail_token.access_token = oauth_data.get("access_token")

    new_refresh_token = oauth_data.get("refresh_token")
    if new_refresh_token:
        gmail_token.refresh_token = new_refresh_token

    gmail_token.expires_at = compute_expiry(oauth_data.get("expires_in"))
    db.session.commit()

    session.pop("gmail_oauth_state", None)
    session.pop("gmail_oauth_next", None)
    session["gmail_success"] = "Gmail connected successfully."

    if next_target == "dashboard":
        return redirect(url_for("auth.dashboard"))
    return redirect(url_for("auth.settings"))


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

    email = session.get("user_email")

    user = {
        "name": email.split("@")[0].title(),
        "email": email,
        "profile_photo": None
    }

    return render_template(
        "dashboard.html",
        user=user,
        email=email
    )


@auth_bp.route("/settings", methods=["GET"])
def settings():
    if not session.get("user_id"):
        return redirect(url_for("auth.login_form"))

    user = _current_user()

    return render_template(
        "settings.html",
        user=user,
        **_settings_context()
    )


@auth_bp.route("/compose", methods=["GET"])
def compose():
    if not session.get("user_id"):
        return redirect(url_for("auth.login_form"))

    return render_template("compose.html", email=session.get("user_email"))


@channel_bp.route("/gmail", methods=["POST", "DELETE"])
def disconnect_gmail():
    user = _current_user()
    if user is None:
        return _json_error("Unauthorized.", 401)

    gmail_token = _gmail_token_for_user(user.id)
    if gmail_token is not None:
        db.session.delete(gmail_token)
        db.session.commit()

    if request.method == "DELETE" or request.is_json:
        return jsonify({"message": "Gmail disconnected."})

    session["gmail_success"] = "Gmail disconnected."
    return redirect(url_for("auth.settings"))

