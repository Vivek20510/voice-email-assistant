from urllib.parse import parse_qs, urlparse

from src.db import db
from src.models import User, UserToken


def test_signup_and_status(client):
    signup_response = client.post(
        "/auth/signup", json={"email": "vivek@example.com", "password": "P@ssw0rd"}
    )
    assert signup_response.status_code == 200
    assert signup_response.json["email"] == "vivek@example.com"

    status_response = client.get("/auth/status")
    assert status_response.status_code == 200
    assert status_response.json["email"] == "vivek@example.com"


def test_signup_duplicate_email(client):
    first_response = client.post(
        "/auth/signup", json={"email": "vivek@example.com", "password": "P@ssw0rd"}
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/auth/signup", json={"email": "vivek@example.com", "password": "NewPass123"}
    )
    assert second_response.status_code == 409
    assert second_response.json["error"] == "Email address already registered."


def test_login_invalid_credentials(client):
    response = client.post(
        "/auth/login", json={"email": "unknown@example.com", "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json["error"] == "Invalid credentials."


def test_signup_missing_fields(client):
    response = client.post("/auth/signup", json={"email": "invalid@example.com"})
    assert response.status_code == 400
    assert response.json["error"] == "Email and password are required."


def test_login_missing_fields(client):
    response = client.post("/auth/login", json={"password": "P@ssw0rd"})
    assert response.status_code == 400
    assert response.json["error"] == "Email and password are required."


def test_dashboard_requires_login(client):
    response = client.get("/auth/dashboard")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_logout_clears_session(client):
    client.post(
        "/auth/signup", json={"email": "vivek@example.com", "password": "P@ssw0rd"}
    )
    logout_response = client.get("/auth/logout")
    assert logout_response.status_code == 302
    assert "/auth/login" in logout_response.headers["Location"]

    status_response = client.get("/auth/status")
    assert status_response.status_code == 401
    assert status_response.json["error"] == "Unauthorized."


def test_google_login_redirects_and_stores_state(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client-id")
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:5000/auth/callback"
    )

    response = client.get("/auth/google")

    assert response.status_code == 302
    assert "accounts.google.com" in response.headers["Location"]

    parsed = urlparse(response.headers["Location"])
    params = parse_qs(parsed.query)
    assert params["client_id"]
    assert params["redirect_uri"]
    assert params["scope"] == ["openid email profile"]

    with client.session_transaction() as session:
        assert session["oauth_state"] == params["state"][0]


def test_google_callback_rejects_invalid_state(client):
    with client.session_transaction() as session:
        session["oauth_state"] = "expected-state"

    response = client.get("/auth/callback?code=test-code&state=wrong-state")

    assert response.status_code == 400
    assert b"Incorrect email or password" not in response.data


def test_google_callback_creates_user_and_logs_in(client, monkeypatch, app):
    def fake_handle_callback(request_url, expected_state):
        assert expected_state == "expected-state"
        assert "code=test-code" in request_url
        return {"email": "oauth@example.com", "name": "OAuth User", "sub": "google-123"}

    monkeypatch.setattr("src.web.auth_routes.handle_callback", fake_handle_callback)

    with client.session_transaction() as session:
        session["oauth_state"] = "expected-state"

    response = client.get("/auth/callback?code=test-code&state=expected-state")

    assert response.status_code == 302
    assert "/auth/dashboard" in response.headers["Location"]

    with app.app_context():
        user = User.query.filter_by(email="oauth@example.com").first()
        assert user is not None
        assert user.password_hash

    with client.session_transaction() as session:
        assert session["user_email"] == "oauth@example.com"
        assert session["user_name"] == "OAuth User"
        assert session["user_id"] == user.id
        assert "oauth_state" not in session


def test_oauth_login_can_access_protected_routes(client, monkeypatch):
    def fake_handle_callback(request_url, expected_state):
        return {"email": "oauth@example.com", "name": "OAuth User", "sub": "google-123"}

    monkeypatch.setattr("src.web.auth_routes.handle_callback", fake_handle_callback)

    with client.session_transaction() as session:
        session["oauth_state"] = "expected-state"

    client.get("/auth/callback?code=test-code&state=expected-state")
    response = client.get("/email/list")

    assert response.status_code == 200
    assert response.json == {"emails": []}


def test_gmail_connect_requires_login(client):
    response = client.get("/auth/gmail/connect")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_gmail_connect_redirects_with_gmail_scopes(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client-id")
    monkeypatch.setenv(
        "GOOGLE_GMAIL_REDIRECT_URI", "http://localhost:5000/auth/gmail/callback"
    )
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )

    response = client.get("/auth/gmail/connect?next=settings")

    assert response.status_code == 302
    parsed = urlparse(response.headers["Location"])
    params = parse_qs(parsed.query)
    assert params["redirect_uri"] == ["http://localhost:5000/auth/gmail/callback"]
    assert "https://www.googleapis.com/auth/gmail.readonly" in params["scope"][0]
    assert "https://www.googleapis.com/auth/gmail.send" in params["scope"][0]

    with client.session_transaction() as session:
        assert session["gmail_oauth_state"] == params["state"][0]
        assert session["gmail_oauth_next"] == "settings"


def test_gmail_callback_rejects_invalid_state_without_logging_out(client):
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )
    with client.session_transaction() as session:
        session["gmail_oauth_state"] = "expected-state"
        session["gmail_oauth_next"] = "settings"

    response = client.get("/auth/gmail/callback?code=test-code&state=wrong-state")

    assert response.status_code == 302
    assert "/auth/settings" in response.headers["Location"]

    status_response = client.get("/auth/status")
    assert status_response.status_code == 200
    assert status_response.json["email"] == "user@example.com"

    settings_response = client.get("/auth/settings")
    assert b"Gmail connection failed." in settings_response.data


def test_gmail_callback_stores_token(client, monkeypatch, app):
    def fake_handle_gmail_callback(request_url, expected_state):
        assert expected_state == "expected-state"
        return {
            "access_token": "gmail-access-token",
            "refresh_token": "gmail-refresh-token",
            "expires_in": 3600,
            "user_info": {"email": "gmail@example.com", "name": "Gmail User"},
        }

    monkeypatch.setattr(
        "src.web.auth_routes.handle_gmail_callback", fake_handle_gmail_callback
    )
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )
    with client.session_transaction() as session:
        session["gmail_oauth_state"] = "expected-state"
        session["gmail_oauth_next"] = "settings"

    response = client.get("/auth/gmail/callback?code=test-code&state=expected-state")

    assert response.status_code == 302
    assert "/auth/settings" in response.headers["Location"]

    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        gmail_token = UserToken.query.filter_by(
            user_id=user.id, service="gmail"
        ).first()
        assert gmail_token is not None
        assert gmail_token.account_email == "gmail@example.com"
        assert gmail_token.access_token == "gmail-access-token"
        assert gmail_token.refresh_token == "gmail-refresh-token"
        assert gmail_token.expires_at is not None


def test_gmail_reconnect_preserves_existing_refresh_token(client, monkeypatch, app):
    def fake_handle_gmail_callback(request_url, expected_state):
        return {
            "access_token": "new-access-token",
            "refresh_token": None,
            "expires_in": 1800,
            "user_info": {"email": "gmail@example.com", "name": "Gmail User"},
        }

    monkeypatch.setattr(
        "src.web.auth_routes.handle_gmail_callback", fake_handle_gmail_callback
    )
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )

    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        token = UserToken(
            user_id=user.id,
            service="gmail",
            account_email="old@example.com",
            access_token="old-access-token",
            refresh_token="existing-refresh-token",
        )
        db.session.add(token)
        db.session.commit()

    with client.session_transaction() as session:
        session["gmail_oauth_state"] = "expected-state"
        session["gmail_oauth_next"] = "settings"

    response = client.get("/auth/gmail/callback?code=test-code&state=expected-state")

    assert response.status_code == 302

    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        gmail_token = UserToken.query.filter_by(
            user_id=user.id, service="gmail"
        ).first()
        assert gmail_token.access_token == "new-access-token"
        assert gmail_token.refresh_token == "existing-refresh-token"
        assert gmail_token.account_email == "gmail@example.com"


def test_disconnect_gmail_requires_login(client):
    response = client.post("/api/channels/gmail")

    assert response.status_code == 401
    assert response.json["error"] == "Unauthorized."


def test_disconnect_gmail_removes_token(client, app):
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )

    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        db.session.add(
            UserToken(
                user_id=user.id,
                service="gmail",
                account_email="gmail@example.com",
                access_token="token",
                refresh_token="refresh",
            )
        )
        db.session.commit()

    response = client.post("/api/channels/gmail")

    assert response.status_code == 302
    assert "/auth/settings" in response.headers["Location"]

    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        assert (
            UserToken.query.filter_by(user_id=user.id, service="gmail").first() is None
        )


def test_settings_page_shows_gmail_connection_state(client, app):
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )

    disconnected_response = client.get("/auth/settings")
    assert b"Connect Gmail" in disconnected_response.data
    assert b"Disconnect Gmail" not in disconnected_response.data

    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        db.session.add(
            UserToken(
                user_id=user.id,
                service="gmail",
                account_email="gmail@example.com",
                access_token="token",
            )
        )
        db.session.commit()

    connected_response = client.get("/auth/settings")
    assert b"Disconnect Gmail" in connected_response.data
    assert b"gmail@example.com" in connected_response.data
