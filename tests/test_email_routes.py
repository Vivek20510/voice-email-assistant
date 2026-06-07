from datetime import datetime, timedelta, timezone

from src.db import db
from src.models import User, UserToken


def _signup(client):
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123", "security_question_1": "What city were you born in?", "security_answer_1": "Mumbai", "security_question_2": "What is your first school?", "security_answer_2": "Central"}
    )


def _attach_gmail_token(app):
    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
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


def test_email_routes_require_login(client):
    list_response = client.get("/email/list")
    assert list_response.status_code == 401
    assert list_response.json["error"] == "Unauthorized."

    send_response = client.post(
        "/email/send", json={"to": "test@example.com", "subject": "Hello"}
    )
    assert send_response.status_code == 401
    assert send_response.json["error"] == "Unauthorized."

    read_response = client.get("/email/read/msg-1")
    assert read_response.status_code == 401
    assert read_response.json["error"] == "Unauthorized."

    api_list = client.get("/api/messages")
    assert api_list.status_code == 401

    api_send = client.post("/api/send", json={"to": "test@example.com", "body": "Hi"})
    assert api_send.status_code == 401


def test_email_routes_require_gmail_connection(client):
    _signup(client)

    list_response = client.get("/email/list")
    assert list_response.status_code == 409
    assert list_response.json["error"] == "Gmail is not connected for this account."

    read_response = client.get("/api/messages/msg-1")
    assert read_response.status_code == 409

    send_response = client.post(
        "/api/send", json={"to": "to@example.com", "body": "Hi"}
    )
    assert send_response.status_code == 409


def test_email_list_routes_return_live_messages(client, app, monkeypatch):
    _signup(client)
    _attach_gmail_token(app)

    def fake_list_emails(
        user_id, limit, page_token=None, label_ids=None, folder="inbox"
    ):
        assert folder == "inbox"
        return {
            "emails": [
                {
                    "id": "msg-1",
                    "gmail_id": "msg-1",
                    "sender": "Alice",
                    "sender_email": "alice@example.com",
                    "to": "user@example.com",
                    "subject": "Hello",
                    "snippet": "Preview",
                    "received_at": "2026-04-22T10:00:00+00:00",
                    "unread": True,
                    "labels": ["INBOX"],
                    "channel": "gmail",
                }
            ],
            "messages": [
                {
                    "id": "msg-1",
                    "gmail_id": "msg-1",
                    "sender": "Alice",
                    "sender_email": "alice@example.com",
                    "to": "user@example.com",
                    "subject": "Hello",
                    "snippet": "Preview",
                    "received_at": "2026-04-22T10:00:00+00:00",
                    "unread": True,
                    "labels": ["INBOX"],
                    "channel": "gmail",
                }
            ],
            "next_page_token": "next-token",
        }

    monkeypatch.setattr("src.web.email_routes.gmail_list_emails", fake_list_emails)

    list_response = client.get("/email/list?limit=5")
    assert list_response.status_code == 200
    assert list_response.json["emails"][0]["id"] == "msg-1"

    api_response = client.get("/api/messages?limit=5")
    assert api_response.status_code == 200
    assert api_response.json["messages"][0]["sender"] == "Alice"


def test_api_messages_fetches_combined_mail_folder_and_count(client, monkeypatch):
    _signup(client)
    calls = []

    def fake_gmail(user_id, limit, page_token=None, label_ids=None, folder="inbox"):
        calls.append(("gmail", folder))
        return {
            "messages": [
                {
                    "id": "gmail-sent-1",
                    "sender": "Gmail Sender",
                    "subject": "Gmail sent",
                    "received_at": "2026-04-22T10:00:00+00:00",
                    "unread": False,
                    "labels": ["SENT"],
                    "channel": "gmail",
                }
            ],
            "emails": [],
            "total_count": 4,
        }

    def fake_outlook(user_id, limit, folder="inbox"):
        calls.append(("outlook", folder))
        return {
            "messages": [
                {
                    "id": "outlook-sent-1",
                    "sender": "Outlook Sender",
                    "subject": "Outlook sent",
                    "received_at": "2026-04-22T11:00:00+00:00",
                    "unread": True,
                    "labels": [],
                    "channel": "outlook",
                }
            ],
            "emails": [],
            "total_count": 3,
        }

    monkeypatch.setattr("src.web.email_routes.gmail_list_emails", fake_gmail)
    monkeypatch.setattr("src.web.email_routes.outlook_list_emails", fake_outlook)

    response = client.get("/api/messages?channel=all&folder=sent&limit=25")

    assert response.status_code == 200
    assert calls == [("gmail", "sent"), ("outlook", "sent")]
    assert response.json["folder"] == "sent"
    assert response.json["channel"] == "all"
    assert response.json["total_count"] == 7
    assert response.json["count"] == 2
    assert response.json["unread_count"] == 1
    assert [message["id"] for message in response.json["messages"]] == [
        "outlook-sent-1",
        "gmail-sent-1",
    ]


def test_api_messages_archive_uses_archive_folder(client, monkeypatch):
    _signup(client)
    folders = []

    def fake_gmail(user_id, limit, page_token=None, label_ids=None, folder="inbox"):
        folders.append(("gmail", folder))
        return {"messages": [], "emails": [], "total_count": 0}

    def fake_outlook(user_id, limit, folder="inbox"):
        folders.append(("outlook", folder))
        return {"messages": [], "emails": [], "total_count": 0}

    monkeypatch.setattr("src.web.email_routes.gmail_list_emails", fake_gmail)
    monkeypatch.setattr("src.web.email_routes.outlook_list_emails", fake_outlook)

    response = client.get("/api/messages?channel=all&folder=archive")

    assert response.status_code == 200
    assert folders == [("gmail", "archive"), ("outlook", "archive")]


def test_read_routes_return_live_message_detail(client, app, monkeypatch):
    _signup(client)
    _attach_gmail_token(app)

    def fake_read_email(user_id, gmail_id):
        assert gmail_id == "msg-1"
        return {
            "id": "msg-1",
            "gmail_id": "msg-1",
            "sender": "Alice",
            "sender_email": "alice@example.com",
            "to": "user@example.com",
            "cc": None,
            "bcc": None,
            "subject": "Hello",
            "body_text": "Body",
            "body_html": "<p>Body</p>",
            "snippet": "Preview",
            "received_at": "2026-04-22T10:00:00+00:00",
            "unread": False,
            "labels": ["INBOX"],
            "channel": "gmail",
        }

    monkeypatch.setattr("src.web.email_routes.gmail_read_email", fake_read_email)

    read_response = client.get("/email/read/msg-1")
    assert read_response.status_code == 200
    assert read_response.json["body_text"] == "Body"

    api_response = client.get("/api/messages/msg-1")
    assert api_response.status_code == 200
    assert api_response.json["body_html"] == "<p>Body</p>"


def test_send_routes_send_gmail_messages(client, app, monkeypatch):
    _signup(client)
    _attach_gmail_token(app)

    def fake_send_email(user_id, to, subject, body, channel=None):
        assert to == "to@example.com"
        assert subject == "Hello"
        assert body == "Hi there"
        return {"status": "sent", "id": "sent-1", "thread_id": "thread-1"}

    monkeypatch.setattr("src.web.email_routes.gmail_send_email", fake_send_email)

    send_response = client.post(
        "/email/send",
        json={"to": "to@example.com", "subject": "Hello", "body": "Hi there"},
    )
    assert send_response.status_code == 200
    assert send_response.json["status"] == "sent"

    api_send = client.post(
        "/api/send",
        json={
            "to": "to@example.com",
            "subject": "Hello",
            "body": "Hi there",
            "channel": "gmail",
        },
    )
    assert api_send.status_code == 200
    assert api_send.json["id"] == "sent-1"


def test_send_routes_validate_payload(client):
    _signup(client)

    missing_body = client.post("/api/send", json={"to": "to@example.com"})
    assert missing_body.status_code == 400
    assert missing_body.json["error"] == "To and body are required."

    unsupported_channel = client.post(
        "/api/send",
        json={
            "to": "to@example.com",
            "body": "Hello",
            "channel": "telegram",
        },
    )
    assert unsupported_channel.status_code == 501
    assert (
        unsupported_channel.json["error"]
        == "Only Gmail sending is supported right now."
    )


def test_email_routes_retry_after_gmail_401(client, app, monkeypatch):
    _signup(client)
    _attach_gmail_token(app)
    calls = {"count": 0}

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        calls["count"] += 1
        if calls["count"] == 1:

            class UnauthorizedResponse:
                status_code = 401

                @staticmethod
                def json():
                    return {"error": {"message": "Invalid Credentials"}}

                @staticmethod
                def raise_for_status():
                    import requests

                    raise requests.HTTPError("401")

            return UnauthorizedResponse()

        class OkResponse:
            status_code = 200

            @staticmethod
            def json():
                return {
                    "id": "msg-1",
                    "snippet": "Preview",
                    "labelIds": ["INBOX"],
                    "payload": {"headers": []},
                }

            @staticmethod
            def raise_for_status():
                return None

        return OkResponse()

    def fake_refresh(user_token):
        user_token.access_token = "refreshed-token"
        return user_token

    monkeypatch.setattr("src.services.email_service.requests.request", fake_request)
    monkeypatch.setattr("src.services.email_service.refresh_gmail_token", fake_refresh)

    response = client.get("/api/messages/msg-1")

    assert response.status_code == 200
    assert calls["count"] == 2

