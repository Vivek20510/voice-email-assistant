from src.services import nlp_service
from src.services.nlp_service import (
    MAX_SUMMARY_INPUT_CHARS,
    SUMMARY_FALLBACK,
    build_email_summary_input,
    summarize_text,
    suggest_replies,
)


def test_summarize_text_uses_shared_ai_service(monkeypatch):
    captured = {}

    def fake_generate_response(prompt):
        captured["prompt"] = prompt
        return "Alice asked for roadmap feedback."

    monkeypatch.setattr(nlp_service, "generate_response", fake_generate_response)

    summary = summarize_text(
        subject="Roadmap review",
        sender="Alice",
        body="Please review the roadmap and send feedback by Friday.",
    )

    assert summary == "Alice asked for roadmap feedback."
    assert "Please review the roadmap" in captured["prompt"]


def test_summarize_text_returns_fallback_on_ai_failure(monkeypatch):
    def fake_generate_response(prompt):
        raise RuntimeError("AI unavailable")

    monkeypatch.setattr(nlp_service, "generate_response", fake_generate_response)

    summary = summarize_text("Hello world")

    assert summary == SUMMARY_FALLBACK


def test_summarize_text_returns_fallback_for_empty_input():
    assert summarize_text("") == SUMMARY_FALLBACK


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


def test_suggest_replies_returns_tone_dict(monkeypatch):
    captured = {}

    def fake_generate_qwen_replies(text, tones=None):
        captured.update({"text": text, "tones": tones})
        return {
            "casual": "Sure, I can help.",
            "formal": "Thank you for your message.",
            "professional": "I will follow up soon.",
        }

    monkeypatch.setattr(
        nlp_service,
        "generate_qwen_replies",
        fake_generate_qwen_replies,
    )

    suggestions = suggest_replies("Can you help me?")

    assert isinstance(suggestions, dict)
    assert set(suggestions) == {"casual", "formal", "professional"}
    assert suggestions["casual"] == "Sure, I can help."
    assert captured == {
        "text": "Can you help me?",
        "tones": ["casual", "formal", "professional"],
    }


def test_suggest_replies_falls_back_for_empty_text():
    suggestions = suggest_replies("")

    assert isinstance(suggestions, dict)
    assert suggestions["professional"]
