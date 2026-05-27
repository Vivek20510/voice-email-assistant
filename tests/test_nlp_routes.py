def test_summarize_route_returns_summary(client):
    response = client.post(
        "/nlp/summarize", json={"text": "This is a test email body."}
    )
    assert response.status_code == 200
    assert "summary" in response.json
    assert isinstance(response.json["summary"], str)


def test_summarize_route_accepts_email_fields(client, monkeypatch):
    captured = {}

    def fake_summarize_text(text=None, *, subject=None, sender=None, body=None):
        captured.update(
            {"text": text, "subject": subject, "sender": sender, "body": body}
        )
        return "Alice needs feedback by Friday."

    monkeypatch.setattr("src.web.nlp_routes.summarize_text", fake_summarize_text)

    response = client.post(
        "/nlp/summarize",
        json={
            "subject": "Q3 report",
            "sender": "Alice",
            "body": "Please review the report by Friday.",
        },
    )

    assert response.status_code == 200
    assert response.json["summary"] == "Alice needs feedback by Friday."
    assert captured == {
        "text": "",
        "subject": "Q3 report",
        "sender": "Alice",
        "body": "Please review the report by Friday.",
    }


def test_suggest_route_returns_suggestions(client):
    response = client.post(
        "/nlp/suggest", json={"text": "Please help with scheduling."}
    )
    assert response.status_code == 200
    assert "suggestions" in response.json
    assert isinstance(response.json["suggestions"], dict)


def test_nlp_route_validation(client):
    response = client.post("/nlp/summarize", json={})
    assert response.status_code == 400
    assert response.json["error"] == "Text is required."


def test_summarize_route_rejects_non_object_payload(client):
    response = client.post("/nlp/summarize", json=["not", "an", "object"])

    assert response.status_code == 400
    assert response.json["error"] == "JSON object payload is required."


def test_summarize_route_rejects_non_string_fields(client):
    response = client.post("/nlp/summarize", json={"body": {"text": "hello"}})

    assert response.status_code == 400
    assert response.json["error"] == "body must be a string."


def test_summarize_route_accepts_whitespace_around_email_fields(client, monkeypatch):
    captured = {}

    def fake_summarize_text(text=None, *, subject=None, sender=None, body=None):
        captured.update(
            {"text": text, "subject": subject, "sender": sender, "body": body}
        )
        return "Trimmed summary."

    monkeypatch.setattr("src.web.nlp_routes.summarize_text", fake_summarize_text)

    response = client.post(
        "/nlp/summarize",
        json={"subject": "  Update  ", "sender": "  Alice  ", "body": "  Hi  "},
    )

    assert response.status_code == 200
    assert response.json["summary"] == "Trimmed summary."
    assert captured == {
        "text": "",
        "subject": "Update",
        "sender": "Alice",
        "body": "Hi",
    }


def test_ai_query_route_requires_object_payload(client):
    response = client.post("/nlp/ai-query", json=["not", "an", "object"])

    assert response.status_code == 400
    assert response.json["success"] is False
    assert response.json["error"] == "Valid JSON payload required."


def test_ai_query_route_requires_query(client):
    response = client.post("/nlp/ai-query", json={"query": "   ", "emails": []})

    assert response.status_code == 400
    assert response.json["success"] is False
    assert response.json["error"] == "Query is required."


def test_ai_query_route_rejects_non_list_emails(client):
    response = client.post(
        "/nlp/ai-query",
        json={"query": "Summarize my inbox", "emails": {"subject": "Hi"}},
    )

    assert response.status_code == 400
    assert response.json["success"] is False
    assert response.json["error"] == "Emails must be a list."


def test_ai_query_route_passes_email_context_to_ai(client, monkeypatch):
    captured = {}

    def fake_generate_response(prompt):
        captured["prompt"] = prompt
        return "Alice asked for feedback by Friday."

    monkeypatch.setattr("src.web.nlp_routes.generate_response", fake_generate_response)

    response = client.post(
        "/nlp/ai-query",
        json={
            "query": "What needs action?",
            "emails": [
                {
                    "sender": "Alice",
                    "subject": "Q3 report",
                    "snippet": "Please send feedback by Friday.",
                    "received_at": "2026-05-25T09:30:00Z",
                    "channel": "gmail",
                    "unread": True,
                    "has_attachments": True,
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.json["query"] == "What needs action?"
    assert response.json["response"] == "Alice asked for feedback by Friday."
    assert response.json["ai_mode"]
    assert "What needs action?" in captured["prompt"]
    assert "Alice" in captured["prompt"]
    assert "Q3 report" in captured["prompt"]
    assert "Please send feedback by Friday." in captured["prompt"]
    assert "unread; has attachments" in captured["prompt"]


def test_ai_query_route_returns_structured_mixed_context_filter(client):
    response = client.post(
        "/nlp/ai-query",
        json={
            "query": "show outlook",
            "emails": [
                {
                    "id": "g-1",
                    "sender": "Alice",
                    "subject": "Gmail report",
                    "channel": "gmail",
                },
                {
                    "id": "o-1",
                    "sender": "Bob",
                    "subject": "Outlook plan",
                    "channel": "outlook",
                    "unread": True,
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.json["intent"] == "filter_outlook"
    assert response.json["context_summary"] == {"total": 2, "gmail": 1, "outlook": 1}
    assert response.json["cards"][0]["id"] == "o-1"
    assert response.json["actions"][0]["type"] == "filter_view"
    assert response.json["actions"][0]["payload"]["channel"] == "outlook"


def test_ai_query_route_filters_unread_attachments_sender_and_subject(client):
    emails = [
        {
            "id": "1",
            "sender": "Alice Cooper",
            "subject": "Budget report",
            "snippet": "Attached PDF",
            "unread": True,
            "has_attachments": True,
            "channel": "gmail",
        },
        {
            "id": "2",
            "sender": "Bob Smith",
            "subject": "Lunch",
            "unread": False,
            "channel": "outlook",
        },
    ]

    unread = client.post("/nlp/ai-query", json={"query": "unread", "emails": emails})
    attachments = client.post(
        "/nlp/ai-query", json={"query": "with attachments", "emails": emails}
    )
    sender = client.post(
        "/nlp/ai-query", json={"query": "from Alice", "emails": emails}
    )
    subject = client.post(
        "/nlp/ai-query", json={"query": "subject Budget", "emails": emails}
    )

    assert unread.json["cards"][0]["id"] == "1"
    assert attachments.json["cards"][0]["has_attachments"] is True
    assert sender.json["cards"][0]["sender"] == "Alice Cooper"
    assert subject.json["cards"][0]["subject"] == "Budget report"


def test_ai_query_route_navigation_intents_return_safe_actions(client):
    settings = client.post(
        "/nlp/ai-query", json={"query": "open settings", "emails": []}
    )
    compose = client.post(
        "/nlp/ai-query", json={"query": "compose email", "emails": []}
    )

    assert settings.status_code == 200
    assert settings.json["actions"][0]["type"] == "open_settings"
    assert compose.status_code == 200
    assert compose.json["actions"][0]["type"] == "open_compose"


def test_ai_query_route_empty_context_does_not_invent(client):
    response = client.post(
        "/nlp/ai-query",
        json={"query": "what needs action", "emails": []},
    )

    assert response.status_code == 200
    assert response.json["intent"] == "insufficient_context"
    assert response.json["cards"] == []
    assert "emails loaded" in response.json["response"]


def test_ai_query_route_rejects_invalid_history(client):
    response = client.post(
        "/nlp/ai-query",
        json={"query": "summarize", "emails": [], "history": {"role": "user"}},
    )

    assert response.status_code == 400
    assert response.json["error"] == "History must be a list."
