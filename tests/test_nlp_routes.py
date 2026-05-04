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
    assert isinstance(response.json["suggestions"], list)


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
