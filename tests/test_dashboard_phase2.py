from datetime import datetime, timedelta, timezone

from src.db import db
from src.models import EmailMessage, User, UserToken


def _seed_dashboard_data(app, email="dash@example.com"):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        now = datetime.now(timezone.utc)

        db.session.add(
            UserToken(user_id=user.id, service="gmail", access_token="token")
        )
        db.session.add_all(
            [
                EmailMessage(
                    user_id=user.id,
                    gmail_id="gmail-1",
                    subject="Project update",
                    body="Here is the project update for today with action items.",
                    to="manager@example.com",
                    created_at=now,
                ),
                EmailMessage(
                    user_id=user.id,
                    gmail_id="gmail-2",
                    subject="Invoice reminder",
                    body="Please review the attached invoice and approve it today.",
                    to="finance@example.com",
                    created_at=now - timedelta(days=1),
                ),
                EmailMessage(
                    user_id=user.id,
                    gmail_id=None,
                    subject="Draft follow up",
                    body="Following up on the client meeting and next steps.",
                    to="client@example.com",
                    created_at=now - timedelta(days=2),
                ),
            ]
        )
        db.session.commit()


def test_dashboard_page_renders_live_sections(client, app):
    client.post(
        "/auth/register",
        json={"email": "dash@example.com", "password": "SecurePass123"},
    )
    _seed_dashboard_data(app)

    response = client.get("/auth/dashboard")
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    assert "data-dashboard-root" in body
    assert "Service status" in body
    assert "AI search" in body
    assert "stats-grid" in body
    assert "messages-list" in body


def test_api_stats_requires_login(client):
    response = client.get("/api/stats")
    assert response.status_code == 401
    assert response.json["error"] == "Unauthorized."


def test_api_stats_returns_expected_keys(client, app):
    client.post(
        "/auth/register",
        json={"email": "dash@example.com", "password": "SecurePass123"},
    )
    _seed_dashboard_data(app)

    response = client.get("/api/stats")
    assert response.status_code == 200
    assert response.json["total_messages"] == 3
    assert response.json["unread_count"] == 2
    assert response.json["draft_count"] == 1
    assert response.json["sent_today"] >= 1
    assert response.json["ai_replies"] >= 0
    assert len(response.json["trends"]) == 7


def test_api_messages_requires_login(client):
    response = client.get("/api/messages")
    assert response.status_code == 401
    assert response.json["error"] == "Unauthorized."


def test_api_messages_supports_filters_and_pagination(client, app):
    client.post(
        "/auth/register",
        json={"email": "dash@example.com", "password": "SecurePass123"},
    )
    _seed_dashboard_data(app)

    response = client.get(
        "/api/messages?folder=inbox&channel=gmail&sort=oldest&limit=1&offset=0"
    )
    assert response.status_code == 200
    assert response.json["meta"]["count"] == 1
    assert response.json["messages"][0]["subject"] == "Invoice reminder"
    assert response.json["messages"][0]["folder"] == "inbox"
    assert response.json["messages"][0]["channel"] == "gmail"


def test_api_ai_search_requires_login(client):
    response = client.post("/api/ai/search", json={"query": "invoice"})
    assert response.status_code == 401
    assert response.json["error"] == "Unauthorized."


def test_api_ai_search_returns_results(client, app):
    client.post(
        "/auth/register",
        json={"email": "dash@example.com", "password": "SecurePass123"},
    )
    _seed_dashboard_data(app)

    response = client.post("/api/ai/search", json={"query": "invoice"})
    assert response.status_code == 200
    assert response.json["type"] == "results"
    assert response.json["query"] == "invoice"
    assert len(response.json["results"]) == 1
    assert response.json["results"][0]["title"] == "Invoice reminder"
