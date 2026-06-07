from urllib.parse import parse_qs, urlparse

from src.db import db
from src.models import User, UserPreference, UserToken
from src.services.auth import hash_password


def _signup_payload(email="user@example.com", password="SecurePass123"):
    return {
        "email": email,
        "password": password,
        "security_question_1": "What city were you born in?",
        "security_answer_1": "Mumbai",
        "security_question_2": "What is your first school's name?",
        "security_answer_2": "Central",
    }


def test_signup_and_status(client, app):
    signup_response = client.post(
        "/auth/signup", json=_signup_payload("vivek@example.com", "P@ssw0rd")
    )
    assert signup_response.status_code == 200
    assert signup_response.json["email"] == "vivek@example.com"

    status_response = client.get("/auth/status")
    assert status_response.status_code == 200
    assert status_response.json["email"] == "vivek@example.com"

    with app.app_context():
        user = User.query.filter_by(email="vivek@example.com").first()
        assert user.security_question_1 == "What city were you born in?"
        assert user.security_answer_1_hash
        assert user.security_question_2 == "What is your first school's name?"
        assert user.security_answer_2_hash


def test_signup_duplicate_email(client):
    first_response = client.post(
        "/auth/signup", json=_signup_payload("vivek@example.com", "P@ssw0rd")
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/auth/signup", json=_signup_payload("vivek@example.com", "NewPass123")
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
    assert (
        response.json["error"]
        == "Email, password, and two security questions/answers are required."
    )


def test_login_missing_fields(client):
    response = client.post("/auth/login", json={"password": "P@ssw0rd"})
    assert response.status_code == 400
    assert response.json["error"] == "Email and password are required."


def test_forgot_password_uses_generic_response_for_unknown_email(client):
    response = client.post(
        "/auth/forgot-password", data={"email": "unknown@example.com"}
    )

    assert response.status_code == 200
    assert b"If that account can be recovered with security questions" in response.data
    assert b"No account found" not in response.data

    with client.session_transaction() as session:
        assert "pw_reset_user_id" not in session
        assert "pw_reset_verified" not in session


def test_forgot_password_redirects_recoverable_user_to_questions(client):
    client.post("/auth/signup", json=_signup_payload("recover@example.com"))
    client.get("/auth/logout")

    response = client.post(
        "/auth/forgot-password", data={"email": "recover@example.com"}
    )

    assert response.status_code == 302
    assert "/auth/verify-security-questions" in response.headers["Location"]

    verify_response = client.get(response.headers["Location"])
    assert verify_response.status_code == 200
    assert b"What city were you born in?" in verify_response.data
    assert b"What is your first school" in verify_response.data


def test_security_answers_allow_password_reset(client):
    client.post(
        "/auth/signup",
        json=_signup_payload("recover@example.com", "OldPass123"),
    )
    client.get("/auth/logout")
    client.post("/auth/forgot-password", data={"email": "recover@example.com"})

    verify_response = client.post(
        "/auth/verify-security-questions",
        data={"security_answer_1": "Mumbai", "security_answer_2": "Central"},
    )
    assert verify_response.status_code == 302
    assert "/auth/reset-password" in verify_response.headers["Location"]

    reset_response = client.post(
        "/auth/reset-password",
        data={"password": "NewPass123", "confirm_password": "Mismatch123"},
    )
    assert reset_response.status_code == 200
    assert b"Passwords do not match." in reset_response.data

    success_response = client.post(
        "/auth/reset-password",
        data={"password": "NewPass123", "confirm_password": "NewPass123"},
    )
    assert success_response.status_code == 302
    assert "/auth/login" in success_response.headers["Location"]

    with client.session_transaction() as session:
        assert "pw_reset_user_id" not in session
        assert "pw_reset_verified" not in session

    login_response = client.post(
        "/auth/login", json={"email": "recover@example.com", "password": "NewPass123"}
    )
    assert login_response.status_code == 200


def test_security_answer_failures_lock_after_five_attempts(client, app):
    client.post("/auth/signup", json=_signup_payload("locked@example.com"))
    client.get("/auth/logout")
    client.post("/auth/forgot-password", data={"email": "locked@example.com"})

    for _ in range(5):
        response = client.post(
            "/auth/verify-security-questions",
            data={"security_answer_1": "wrong", "security_answer_2": "wrong"},
        )

    assert response.status_code == 200
    assert b"Too many failed attempts" in response.data

    with app.app_context():
        user = User.query.filter_by(email="locked@example.com").first()
        assert user.security_failed_attempts == 5
        assert user.security_locked_until is not None

    locked_response = client.get("/auth/verify-security-questions")
    assert locked_response.status_code == 200
    assert b"Try again in" in locked_response.data


def test_user_without_questions_cannot_reach_blank_question_page(client, app):
    with app.app_context():
        user = User(email="legacy@example.com", password_hash=hash_password("Pass1234"))
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    forgot_response = client.post(
        "/auth/forgot-password", data={"email": "legacy@example.com"}
    )
    assert forgot_response.status_code == 200
    assert b"If that account can be recovered with security questions" in forgot_response.data

    with client.session_transaction() as session:
        assert "pw_reset_user_id" not in session
        session["pw_reset_user_id"] = user_id

    verify_response = client.get("/auth/verify-security-questions")
    assert verify_response.status_code == 302
    assert "/auth/forgot-password" in verify_response.headers["Location"]


def test_dashboard_requires_login(client):
    response = client.get("/auth/dashboard")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_logout_clears_session(client):
    client.post(
        "/auth/signup", json=_signup_payload("vivek@example.com", "P@ssw0rd")
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

    assert response.status_code == 409
    assert response.json["error"] == "Gmail is not connected for this account."


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
        "/auth/signup", json=_signup_payload()
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
        "/auth/signup", json=_signup_payload()
    )
    with client.session_transaction() as session:
        session["gmail_oauth_state"] = "expected-state"
        session["gmail_oauth_next"] = "settings"

    response = client.get("/auth/gmail/callback?code=test-code&state=wrong-state")

    assert response.status_code == 302
    assert "/auth/dashboard?page=settings&tab=channels" in response.headers["Location"]

    status_response = client.get("/auth/status")
    assert status_response.status_code == 200
    assert status_response.json["email"] == "user@example.com"

    settings_response = client.get("/auth/settings", follow_redirects=True)
    assert b"Gmail connection failed" in settings_response.data


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
        "/auth/signup", json=_signup_payload()
    )
    with client.session_transaction() as session:
        session["gmail_oauth_state"] = "expected-state"
        session["gmail_oauth_next"] = "settings"

    response = client.get("/auth/gmail/callback?code=test-code&state=expected-state")

    assert response.status_code == 302
    assert "/auth/dashboard?page=settings&tab=channels" in response.headers["Location"]

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
        "/auth/signup", json=_signup_payload()
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
        "/auth/signup", json=_signup_payload()
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
    assert "/auth/dashboard?page=settings&tab=channels" in response.headers["Location"]

    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        assert (
            UserToken.query.filter_by(user_id=user.id, service="gmail").first() is None
        )


def test_settings_page_shows_gmail_connection_state(client, app):
    client.post(
        "/auth/signup", json=_signup_payload()
    )

    disconnected_response = client.get("/auth/settings", follow_redirects=True)
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

    connected_response = client.get("/auth/settings", follow_redirects=True)
    assert b"Disconnect Gmail" in connected_response.data
    assert b"gmail@example.com" in connected_response.data


def test_settings_route_redirects_to_dashboard_settings(client):
    client.post(
        "/auth/signup", json=_signup_payload()
    )

    response = client.get("/auth/settings")

    assert response.status_code == 302
    assert "/auth/dashboard?page=settings&tab=channels" in response.headers["Location"]


def test_dashboard_contains_inbox_and_settings_bootstrap_state(client):
    client.post(
        "/auth/signup", json=_signup_payload()
    )

    response = client.get("/auth/dashboard?page=settings&tab=channels")

    assert response.status_code == 200
    assert b'id="dashboard-state"' in response.data
    assert b'data-initial-page="settings"' in response.data
    assert b'data-initial-tab="channels"' in response.data
    assert b'<a class="nav-brand" href="/auth/dashboard">' in response.data
    assert b'id="dashboard-body"' in response.data
    assert b'id="dashboard-title"' in response.data
    assert b'id="dashboard-toolbar-actions"' in response.data
    assert b'id="inbox-content"' in response.data
    assert b'id="dashboard-ai-panel"' in response.data
    assert b'id="notification-toggle"' in response.data
    assert b'id="notification-count"' in response.data
    assert b'id="notification-menu"' in response.data
    assert b'id="notification-list"' in response.data
    assert b"Loading inbox..." in response.data
    assert b"Connect Gmail" in response.data
    assert b"js/message_summary.js" in response.data
    assert response.data.find(b"js/message_summary.js") < response.data.find(
        b"js/dashboard.js"
    )


def test_message_view_requires_login(client):
    response = client.get("/auth/message/msg-1")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_message_view_renders_placeholder_content(client):
    client.post(
        "/auth/signup", json=_signup_payload()
    )

    response = client.get(
        "/auth/message/msg-1?folder=inbox&channel=gmail&page=dashboard"
    )

    assert response.status_code == 200
    assert b"Message" in response.data
    assert b"AI Summary" in response.data
    assert b"AI-Suggested Replies" in response.data
    assert b'id="summary-text"' in response.data
    assert b'data-summary-url="/nlp/summarize"' in response.data
    assert b'data-subject="Q3 Report Review - Feedback Needed"' in response.data
    assert b'data-sender="Alice Rodriguez"' in response.data
    assert b"data-body=" in response.data
    assert b'id="read-aloud-btn"' in response.data
    assert b'id="message-body"' in response.data
    assert b'id="reply-btn"' in response.data
    assert b'id="forward-btn"' in response.data
    assert b'id="archive-btn"' in response.data
    assert b'id="delete-btn"' in response.data
    assert b'id="suggestions-list"' in response.data
    assert b'id="generate-replies-btn"' in response.data
    assert b"reply_suggestions.js" in response.data
    assert b"Alice Rodriguez" in response.data
    assert b"Q3 Report Review - Feedback Needed" in response.data
    assert (
        b"/auth/dashboard?page=dashboard&amp;folder=inbox&amp;channel=gmail"
        in response.data
    )
    assert b"message_summary.js" in response.data
    assert b"|tojson" not in response.data
    assert b"{{" not in response.data
    assert b'fetch("/nlp/summarize"' not in response.data


def test_privacy_preferences_can_disable_and_enable_ai_data_usage(client, app):
    client.post(
        "/auth/signup", json=_signup_payload()
    )

    disabled_response = client.post("/auth/update-privacy-preferences", data={})

    assert disabled_response.status_code == 302
    assert (
        "/auth/dashboard?page=settings&tab=security"
        in disabled_response.headers["Location"]
    )

    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        preference = UserPreference.query.filter_by(user_id=user.id).first()
        assert preference.ai_data_usage_enabled is False

    disabled_page = client.get("/auth/dashboard?page=settings&tab=security")
    assert b'name="ai_data_usage_enabled" checked' not in disabled_page.data

    enabled_response = client.post(
        "/auth/update-privacy-preferences",
        json={"ai_data_usage_enabled": True},
    )

    assert enabled_response.status_code == 200
    assert enabled_response.json == {
        "success": True,
        "ai_data_usage_enabled": True,
    }

    enabled_page = client.get("/auth/dashboard?page=settings&tab=security")
    assert b'name="ai_data_usage_enabled" checked' in enabled_page.data

