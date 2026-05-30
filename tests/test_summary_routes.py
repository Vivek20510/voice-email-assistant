class FakeSummaryEngine:
    def __init__(self):
        self.last_engine_mode = "hf_api"
        self.captured_text = None

    def generate_summary(self, text):
        self.captured_text = text
        return "A concise summary."


def test_ai_summary_route_returns_summary(client, monkeypatch):
    fake_engine = FakeSummaryEngine()
    monkeypatch.setattr("src.web.summary_routes.engine", fake_engine)

    response = client.post(
        "/ai/summary",
        json={
            "text": (
                "Alice shared the quarterly roadmap and asked the team to "
                "send feedback before Friday afternoon."
            )
        },
    )

    assert response.status_code == 200
    assert response.json == {
        "success": True,
        "summary": "A concise summary.",
        "engine": "hf_api",
    }
    assert fake_engine.captured_text.startswith("Alice shared")


def test_ai_summary_route_accepts_email_fields(client, monkeypatch):
    fake_engine = FakeSummaryEngine()
    monkeypatch.setattr("src.web.summary_routes.engine", fake_engine)

    response = client.post(
        "/ai/summary",
        json={
            "subject": "Q3 report",
            "sender": "Alice",
            "body": "Please review the report by Friday.",
        },
    )

    assert response.status_code == 200
    assert response.json["summary"] == "A concise summary."
    assert fake_engine.captured_text == (
        "Subject: Q3 report Sender: Alice Body: Please review the report by Friday."
    )


def test_ai_summary_route_rejects_empty_payload(client):
    response = client.post("/ai/summary", json={})

    assert response.status_code == 400
    assert response.json == {"success": False, "error": "Text is required."}


def test_ai_summary_route_rejects_non_object_payload(client):
    response = client.post("/ai/summary", json=["not", "an", "object"])

    assert response.status_code == 400
    assert response.json == {
        "success": False,
        "error": "JSON object payload is required.",
    }


def test_ai_summary_route_rejects_invalid_json(client):
    response = client.post(
        "/ai/summary",
        data="not json",
        content_type="text/plain",
    )

    assert response.status_code == 400
    assert response.json == {
        "success": False,
        "error": "Valid JSON payload required.",
    }


def test_ai_summary_route_rejects_non_string_fields(client):
    text_response = client.post("/ai/summary", json={"text": {"value": "hello"}})
    body_response = client.post("/ai/summary", json={"body": {"value": "hello"}})

    assert text_response.status_code == 400
    assert text_response.json == {
        "success": False,
        "error": "text must be a string.",
    }
    assert body_response.status_code == 400
    assert body_response.json == {
        "success": False,
        "error": "body must be a string.",
    }
