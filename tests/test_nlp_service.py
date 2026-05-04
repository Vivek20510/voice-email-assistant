from src.services import nlp_service
from src.services.nlp_service import (
    MAX_SUMMARY_INPUT_CHARS,
    SUMMARY_FALLBACK,
    SUMMARY_LOADING_FALLBACK,
    build_email_summary_input,
    summarize_text,
    suggest_replies,
)


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise nlp_service.requests.HTTPError("HF request failed")


def test_summarize_text_returns_bart_summary(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "test-token")

    def fake_post(url, headers, json, timeout):
        assert url.endswith("/facebook/bart-large-cnn")
        assert headers["Authorization"] == "Bearer test-token"
        assert "Please review the roadmap" in json["inputs"]
        assert timeout == nlp_service.HF_REQUEST_TIMEOUT_SECONDS
        return DummyResponse([{"summary_text": "Alice asked for roadmap feedback."}])

    monkeypatch.setattr(nlp_service.requests, "post", fake_post)

    summary = summarize_text(
        subject="Roadmap review",
        sender="Alice",
        body="Please review the roadmap and send feedback by Friday.",
    )

    assert summary == "Alice asked for roadmap feedback."


def test_summarize_text_returns_fallback_without_token(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)

    summary = summarize_text("Hello world")

    assert summary == SUMMARY_FALLBACK


def test_summarize_text_returns_fallback_on_api_failure(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "test-token")

    def fake_post(url, headers, json, timeout):
        raise nlp_service.requests.Timeout("slow model")

    monkeypatch.setattr(nlp_service.requests, "post", fake_post)

    summary = summarize_text("Hello world")

    assert summary == SUMMARY_FALLBACK


def test_summarize_text_handles_hf_cold_start(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "test-token")

    def fake_post(url, headers, json, timeout):
        return DummyResponse(
            {
                "error": "Model facebook/bart-large-cnn is currently loading",
                "estimated_time": 12.5,
            },
            status_code=503,
        )

    monkeypatch.setattr(nlp_service.requests, "post", fake_post)

    summary = summarize_text("Please summarize this email.")

    assert summary == SUMMARY_LOADING_FALLBACK


def test_summarize_text_returns_fallback_for_unexpected_payload(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "test-token")

    def fake_post(url, headers, json, timeout):
        return DummyResponse({"generated_text": "Wrong task output"})

    monkeypatch.setattr(nlp_service.requests, "post", fake_post)

    summary = summarize_text("Please summarize this email.")

    assert summary == SUMMARY_FALLBACK


def test_build_email_summary_input_normalizes_and_trims_long_email():
    long_body = "hello\n\n" * (MAX_SUMMARY_INPUT_CHARS + 100)

    summary_input = build_email_summary_input(
        subject="Quarterly   update",
        sender="Alice\nRodriguez",
        body=long_body,
    )

    assert summary_input.startswith(
        "Subject: Quarterly update Sender: Alice Rodriguez Body:"
    )
    assert "\n" not in summary_input
    assert len(summary_input) == MAX_SUMMARY_INPUT_CHARS


def test_suggest_replies_returns_list():
    suggestions = suggest_replies("Can you help me?")
    assert isinstance(suggestions, list)
    assert len(suggestions) >= 1
