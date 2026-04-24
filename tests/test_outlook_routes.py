"""Integration tests for Outlook routes."""


def test_outlook_toggle_requires_login(client):
    """Test that POST /api/channels/outlook requires authentication.

    Edge case: Unauthenticated request should return 401.
    """
    response = client.post("/api/channels/outlook", json={"enabled": True})

    assert response.status_code == 401
    assert response.json["error"] == "Unauthorized."


def test_outlook_toggle_sets_session_enabled(client):
    """Test that POST /api/channels/outlook sets session flag."""
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )

    response = client.post("/api/channels/outlook", json={"enabled": True})

    assert response.status_code == 200
    assert response.json["outlook_enabled"] is True

    with client.session_transaction() as sess:
        assert sess.get("outlook_enabled") is True


def test_outlook_toggle_sets_session_disabled(client):
    """Test that POST /api/channels/outlook can disable Outlook."""
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )

    client.post("/api/channels/outlook", json={"enabled": True})
    response = client.post("/api/channels/outlook", json={"enabled": False})

    assert response.status_code == 200
    assert response.json["outlook_enabled"] is False

    with client.session_transaction() as sess:
        assert sess.get("outlook_enabled") is False


def test_outlook_inbox_requires_login(client):
    """Test that GET /api/outlook/inbox requires authentication.

    Edge case: Unauthenticated request should return 401.
    """
    response = client.get("/api/outlook/inbox")

    assert response.status_code == 401
    assert response.json["error"] == "Unauthorized."


def test_outlook_inbox_requires_enabled(client):
    """Test that GET /api/outlook/inbox requires outlook_enabled session flag."""
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )

    response = client.get("/api/outlook/inbox")

    assert response.status_code == 409
    assert response.json["error"] == "Outlook not enabled."


def test_outlook_inbox_returns_error_when_unavailable(client, monkeypatch):
    """Test that GET /api/outlook/inbox returns 503 when Outlook unavailable."""
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )
    client.post("/api/channels/outlook", json={"enabled": True})

    # Mock is_outlook_available to return False
    from src.services import outlook_service

    monkeypatch.setattr(outlook_service, "is_outlook_available", lambda: False)

    response = client.get("/api/outlook/inbox")

    assert response.status_code == 503
    assert "not installed" in response.json["error"].lower()


def test_outlook_inbox_returns_empty_list_when_no_messages(client, monkeypatch):
    """Test that GET /api/outlook/inbox returns empty list when no messages."""
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )
    client.post("/api/channels/outlook", json={"enabled": True})

    # Mock list_emails to return empty list
    def mock_list_emails(*args, **kwargs):
        return {"emails": [], "messages": [], "next_page_token": None}

    from src.web import email_routes

    monkeypatch.setattr(email_routes, "outlook_list_emails", mock_list_emails)

    response = client.get("/api/outlook/inbox")

    assert response.status_code == 200
    assert response.json["emails"] == []
    assert response.json["messages"] == []


def test_outlook_inbox_returns_messages_when_available(client, monkeypatch):
    """Test that GET /api/outlook/inbox returns messages when Outlook available."""
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )
    client.post("/api/channels/outlook", json={"enabled": True})

    # Mock list_emails to return sample messages
    def mock_list_emails(*args, **kwargs):
        return {
            "emails": [
                {
                    "id": "dGVzdF9pZA==",
                    "sender": "Alice",
                    "subject": "Test Email",
                    "snippet": "Test snippet",
                    "received_at": "2026-04-23T10:30:00+00:00",
                    "channel": "outlook",
                }
            ],
            "messages": [
                {
                    "id": "dGVzdF9pZA==",
                    "sender": "Alice",
                    "subject": "Test Email",
                    "snippet": "Test snippet",
                    "received_at": "2026-04-23T10:30:00+00:00",
                    "channel": "outlook",
                }
            ],
            "next_page_token": None,
        }

    from src.web import email_routes

    monkeypatch.setattr(email_routes, "outlook_list_emails", mock_list_emails)

    response = client.get("/api/outlook/inbox?limit=10")

    assert response.status_code == 200
    assert len(response.json["emails"]) == 1
    assert response.json["emails"][0]["subject"] == "Test Email"


def test_outlook_inbox_detail_requires_login(client):
    """Test that GET /api/outlook/inbox/<id> requires authentication.

    Edge case: Unauthenticated request should return 401.
    """
    response = client.get("/api/outlook/inbox/dGVzdF9pZA==")

    assert response.status_code == 401


def test_outlook_inbox_detail_requires_enabled(client):
    """Test that GET /api/outlook/inbox/<id> requires outlook_enabled."""
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )

    response = client.get("/api/outlook/inbox/dGVzdF9pZA==")

    assert response.status_code == 409


def test_outlook_inbox_detail_returns_message(client, monkeypatch):
    """Test that GET /api/outlook/inbox/<id> returns message detail."""
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )
    client.post("/api/channels/outlook", json={"enabled": True})

    # Mock read_email to return sample message
    def mock_read_email(*args, **kwargs):
        return {
            "id": "dGVzdF9pZA==",
            "sender": "Alice",
            "sender_email": "alice@example.com",
            "to": "user@example.com",
            "subject": "Test Email",
            "body_text": "This is a test email.",
            "body_html": None,
            "received_at": "2026-04-23T10:30:00+00:00",
            "channel": "outlook",
        }

    from src.web import email_routes

    monkeypatch.setattr(email_routes, "outlook_read_email", mock_read_email)

    response = client.get("/api/outlook/inbox/dGVzdF9pZA==")

    assert response.status_code == 200
    assert response.json["subject"] == "Test Email"
    assert response.json["body_text"] == "This is a test email."


def test_outlook_inbox_detail_returns_error_when_not_found(client, monkeypatch):
    """Test that GET /api/outlook/inbox/<id> returns 404 when message not found."""
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )
    client.post("/api/channels/outlook", json={"enabled": True})

    from src.services.outlook_service import OutlookServiceError
    from src.web import email_routes

    def mock_read_email_error(*args, **kwargs):
        raise OutlookServiceError("Message not found.", 404)

    monkeypatch.setattr(email_routes, "outlook_read_email", mock_read_email_error)

    response = client.get("/api/outlook/inbox/invalid_id")

    assert response.status_code == 404
