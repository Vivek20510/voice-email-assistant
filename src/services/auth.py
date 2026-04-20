import os
import secrets
import urllib.parse

import bcrypt
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
SCOPES = "openid email profile"


def _client_id() -> str | None:
    return os.getenv("GOOGLE_CLIENT_ID")


def _client_secret() -> str | None:
    return os.getenv("GOOGLE_CLIENT_SECRET")


def _redirect_uri() -> str:
    return os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:5000/auth/callback")


def hash_password(password: str) -> str:
    """Hash a plaintext password for secure storage."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against its hashed value."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))



def get_auth_url() -> tuple[str, str]:
    """Build the Google OAuth authorization URL and state token."""
    client_id = _client_id()
    if not client_id:
        raise ValueError("Missing GOOGLE_CLIENT_ID configuration.")

    state = secrets.token_urlsafe(32)
    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return auth_url, state


def handle_callback(request_url: str, expected_state: str | None) -> dict:
    """Validate the callback and return Google user info."""
    if not expected_state:
        raise ValueError("Missing OAuth state in session.")

    client_id = _client_id()
    client_secret = _client_secret()
    if not client_id or not client_secret:
        raise ValueError("Missing Google OAuth client configuration.")

    parsed = urllib.parse.urlparse(request_url)
    params = urllib.parse.parse_qs(parsed.query)

    callback_state = params.get("state", [None])[0]
    if callback_state != expected_state:
        raise ValueError("Invalid OAuth state.")

    error = params.get("error", [None])[0]
    if error:
        raise ValueError(f"Google OAuth error: {error}")

    code = params.get("code", [None])[0]
    if not code:
        raise ValueError("Missing authorization code.")

    token_response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": _redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    token_response.raise_for_status()
    token_data = token_response.json()

    access_token = token_data.get("access_token")
    if not access_token:
        raise ValueError("Missing access token in OAuth response.")

    user_info_response = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    user_info_response.raise_for_status()
    user_info = user_info_response.json()

    if not user_info.get("email"):
        raise ValueError("Google account did not return an email address.")

    return user_info

