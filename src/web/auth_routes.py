from flask import Blueprint, redirect, request, session, url_for, render_template
from src.services.auth import get_auth_url, handle_callback

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/auth/login")
def login():
    if session.get("user_email"):
        return redirect(url_for("auth.dashboard"))
    return render_template("login.html")

@auth_bp.route("/auth/google")
def google_login():
    session.clear()
    auth_url, state = get_auth_url()
    session["oauth_state"] = state
    return redirect(auth_url)

@auth_bp.route("/auth/callback")
def callback():
    try:
        user_info = handle_callback(request.url, session.get("oauth_state"))
        session["user_email"] = user_info.get("email")
        session["user_name"] = user_info.get("name")
        return redirect(url_for("auth.dashboard"))
    except Exception as e:
        print(f"OAuth Error: {e}")
        session.clear()
        return f"OAuth Error: {str(e)}", 500

@auth_bp.route("/dashboard")
def dashboard():
    if not session.get("user_email"):
        return redirect(url_for("auth.login"))
    return render_template("dashboard.html",
                           email=session.get("user_email"),
                           user_name=session.get("user_name"),
                           services={"gmail": False, "telegram": False})

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))