from src.services.nlp_service import summarize_text, suggest_replies


def test_summarize_text_returns_placeholder():
    summary = summarize_text('Hello world')
    assert isinstance(summary, str)
    assert 'placeholder summary' in summary.lower()


def test_suggest_replies_returns_list():
    suggestions = suggest_replies('Can you help me?')
    assert isinstance(suggestions, list)
    assert len(suggestions) >= 1
