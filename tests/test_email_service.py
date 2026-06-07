import base64
from datetime import datetime, timedelta, timezone

import requests

from src.db import db
from src.models import User, UserToken
from src.services import email_service


class DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


def _gmail_body(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")


def _create_connected_user(app):
    with app.app_context():
        user = User(email="user@example.com", password_hash="hashed-password")
        db.session.add(user)
        db.session.commit()

        token = UserToken(
            user_id=user.id,
            service="gmail",
            account_email="gmail@example.com",
            access_token="access-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.session.add(token)
        db.session.commit()
        return user.id


def test_list_emails_normalizes_gmail_messages(app, monkeypatch):
    user_id = _create_connected_user(app)

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/messages"):
            return DummyResponse(
                payload={
                    "messages": [{"id": "msg-1"}],
                    "nextPageToken": "next-token",
                }
            )

        return DummyResponse(
            payload={
                "id": "msg-1",
                "snippet": "A quick summary",
                "labelIds": ["INBOX", "UNREAD"],
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [
                        {"name": "From", "value": "Alice <alice@example.com>"},
                        {"name": "To", "value": "user@example.com"},
                        {"name": "Subject", "value": "Hello"},
                        {"name": "Date", "value": "Mon, 22 Apr 2026 10:00:00 +0000"},
                    ],
                    "body": {"data": _gmail_body("Plain body")},
                },
            }
        )

    monkeypatch.setattr("src.services.email_service.requests.request", fake_request)

    with app.app_context():
        result = email_service.list_emails(user_id, limit=10)

    assert result["next_page_token"] == "next-token"
    assert result["emails"][0]["id"] == "msg-1"
    assert result["emails"][0]["sender"] == "Alice"
    assert result["emails"][0]["sender_email"] == "alice@example.com"
    assert result["emails"][0]["unread"] is True
    assert result["messages"][0]["subject"] == "Hello"


def test_list_emails_maps_gmail_folders_to_labels_and_archive_query(
    app, monkeypatch
):
    user_id = _create_connected_user(app)
    seen = {}
    current = {"folder": None}

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/messages"):
            seen[current["folder"]] = dict(params)
            return DummyResponse(payload={"messages": [], "resultSizeEstimate": 9})
        raise AssertionError("No message detail should be fetched for an empty list")

    monkeypatch.setattr("src.services.email_service.requests.request", fake_request)

    folder_expectations = {
        "inbox": {"labelIds": ["INBOX"]},
        "draft": {"labelIds": ["DRAFT"]},
        "sent": {"labelIds": ["SENT"]},
        "trash": {"labelIds": ["TRASH"]},
        "archive": {"q": email_service.GMAIL_ARCHIVE_QUERY},
    }

    with app.app_context():
        for folder in folder_expectations:
            current["folder"] = folder
            result = email_service.list_emails(user_id, limit=10, folder=folder)
            assert result["total_count"] == 9

    for folder, expected in folder_expectations.items():
        for key, value in expected.items():
            assert seen[folder][key] == value


def test_read_email_handles_multipart_payload(app, monkeypatch):
    user_id = _create_connected_user(app)

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        return DummyResponse(
            payload={
                "id": "msg-2",
                "snippet": "Multipart snippet",
                "labelIds": ["INBOX"],
                "payload": {
                    "mimeType": "multipart/alternative",
                    "headers": [
                        {"name": "From", "value": "Bob <bob@example.com>"},
                        {"name": "To", "value": "user@example.com"},
                        {"name": "Subject", "value": "Status Update"},
                    ],
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {"data": _gmail_body("Plain section")},
                        },
                        {
                            "mimeType": "text/html",
                            "body": {"data": _gmail_body("<p>HTML section</p>")},
                        },
                    ],
                },
            }
        )

    monkeypatch.setattr("src.services.email_service.requests.request", fake_request)

    with app.app_context():
        result = email_service.read_email(user_id, "msg-2")

    assert result["body_text"] == "Plain section"
    assert result["body_html"] == "<p>HTML section</p>"
    assert result["subject"] == "Status Update"
    assert result["channel"] == "gmail"


def test_send_email_encodes_rfc2822_and_calls_gmail(app, monkeypatch):
    user_id = _create_connected_user(app)
    seen = {}

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        seen["method"] = method
        seen["url"] = url
        seen["json"] = json
        return DummyResponse(payload={"id": "sent-1", "threadId": "thread-1"})

    monkeypatch.setattr("src.services.email_service.requests.request", fake_request)

    with app.app_context():
        result = email_service.send_email(
            user_id, "dest@example.com", "Hello", "Message body"
        )

    raw_message = base64.urlsafe_b64decode(seen["json"]["raw"]).decode("utf-8")
    assert seen["method"] == "POST"
    assert seen["url"].endswith("/messages/send")
    assert "To: dest@example.com" in raw_message
    assert "Subject: Hello" in raw_message
    assert "Message body" in raw_message
    assert result["status"] == "sent"
    assert result["id"] == "sent-1"


def test_refresh_gmail_token_updates_stored_token(app, monkeypatch):
    user_id = _create_connected_user(app)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")

    def fake_post(url, data=None, timeout=None):
        return DummyResponse(payload={"access_token": "new-access", "expires_in": 3600})

    monkeypatch.setattr("src.services.email_service.requests.post", fake_post)

    with app.app_context():
        token = UserToken.query.filter_by(user_id=user_id, service="gmail").first()
        email_service.refresh_gmail_token(token)
        db.session.refresh(token)
        assert token.access_token == "new-access"
        assert token.expires_at is not None


def test_expired_token_without_refresh_token_requires_reconnect(app):
    with app.app_context():
        user = User(email="user@example.com", password_hash="hashed-password")
        db.session.add(user)
        db.session.commit()
        db.session.add(
            UserToken(
                user_id=user.id,
                service="gmail",
                account_email="gmail@example.com",
                access_token="expired-token",
                refresh_token=None,
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            )
        )
        db.session.commit()

        try:
            email_service.list_emails(user.id)
        except email_service.GmailConnectionError as exc:
            assert exc.status_code == 409
            assert "reconnect Gmail" in exc.message
        else:
            raise AssertionError("Expected GmailConnectionError for expired token")
