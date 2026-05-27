import os

import secrets

import urllib.parse

from datetime import datetime, timedelta, timezone


import bcrypt

import requests

from dotenv import load_dotenv

load_dotenv()


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

LOGIN_SCOPES = "openid email profile"

GMAIL_SCOPES = " ".join(
    [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ]
)


def _client_id() -> str | None:

    return os.getenv("GOOGLE_CLIENT_ID")


def _client_secret() -> str | None:

    return os.getenv("GOOGLE_CLIENT_SECRET")


def _login_redirect_uri() -> str:

    return os.getenv(
        "GOOGLE_LOGIN_REDIRECT_URI",
        os.getenv(
            "GOOGLE_OAUTH_REDIRECT_URI",
            os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/auth/callback"),
        ),
    )


def _gmail_redirect_uri() -> str:

    return os.getenv(
        "GOOGLE_GMAIL_REDIRECT_URI",
        os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/auth/gmail/callback"),
    )


def hash_password(password: str) -> str:
    """Hash a plaintext password for secure storage."""

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against its hashed value."""

    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def get_auth_url() -> tuple[str, str]:
    """Build the Google OAuth authorization URL and state token."""

    return build_auth_url(scopes=LOGIN_SCOPES, redirect_uri=_login_redirect_uri())


def get_gmail_auth_url() -> tuple[str, str]:
    """Build the Gmail authorization URL and state token."""

    return build_auth_url(scopes=GMAIL_SCOPES, redirect_uri=_gmail_redirect_uri())


def build_auth_url(*, scopes: str, redirect_uri: str) -> tuple[str, str]:
    """Build a Google OAuth authorization URL for the supplied scope set."""

    client_id = _client_id()

    if not client_id:

        raise ValueError("Missing GOOGLE_CLIENT_ID configuration.")

    state = secrets.token_urlsafe(32)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scopes,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    return auth_url, state


def handle_callback(request_url: str, expected_state: str | None) -> dict:
    """Validate the callback and return Google user info."""

    return handle_oauth_callback(
        request_url,
        expected_state,
        redirect_uri=_login_redirect_uri(),
    )["user_info"]


def handle_gmail_callback(request_url: str, expected_state: str | None) -> dict:
    """Validate the Gmail callback and return token data plus user info."""

    return handle_oauth_callback(
        request_url,
        expected_state,
        redirect_uri=_gmail_redirect_uri(),
    )


def handle_oauth_callback(
    request_url: str, expected_state: str | None, *, redirect_uri: str
) -> dict:
    """Validate the callback and return token data plus Google user info."""

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
            "redirect_uri": redirect_uri,
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

    return {
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token"),
        "expires_in": token_data.get("expires_in"),
        "token_type": token_data.get("token_type"),
        "scope": token_data.get("scope"),
        "user_info": user_info,
    }


def compute_expiry(expires_in: int | None) -> datetime | None:
    """Convert OAuth expires_in seconds into an absolute UTC datetime."""

    if expires_in is None:

        return None

    return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
