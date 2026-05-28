from src.services import qwen_draft_service


def test_generate_qwen_drafts_uses_subject_text_for_fallback(monkeypatch):
    monkeypatch.setattr(qwen_draft_service, "load_local_model", lambda: False)
    monkeypatch.setattr(qwen_draft_service, "load_hf_api", lambda: False)

    drafts = qwen_draft_service.generate_qwen_drafts(
        "Project kickoff meeting",
        tones=["professional"],
    )

    assert "professional" in drafts
    assert "Project kickoff meeting" in drafts["professional"]
    assert "reviewed your message" not in drafts["professional"]


def test_generate_qwen_drafts_accepts_short_subject(monkeypatch):
    monkeypatch.setattr(qwen_draft_service, "load_local_model", lambda: False)
    monkeypatch.setattr(qwen_draft_service, "load_hf_api", lambda: False)

    drafts = qwen_draft_service.generate_qwen_drafts("Budget", tones=["formal"])

    assert "Budget" in drafts["formal"]
