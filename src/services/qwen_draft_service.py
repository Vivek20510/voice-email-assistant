"""Qwen email draft generator backed by the shared lazy AI service."""

from __future__ import annotations

import re

from src.services.ai_service import generate_response

_FALLBACK_DRAFTS = {
    "casual": (
        "Hi,\n\n"
        "Thanks for your message. I will take a look and get back to you soon.\n\n"
        "Best regards"
    ),
    "formal": (
        "Dear Sir/Madam,\n\n"
        "Thank you for your email. I will review the details carefully and respond "
        "with an update shortly.\n\nSincerely"
    ),
    "professional": (
        "Hello,\n\n"
        "Thank you for reaching out. I have reviewed your message and will follow "
        "up with the necessary information shortly.\n\nBest regards"
    ),
}

_TONE_LABEL = {
    "casual": "casual and friendly",
    "formal": "formal and polished",
    "professional": "professional and business appropriate",
}


def _build_prompt(text: str, tone: str) -> str:
    label = _TONE_LABEL.get(tone, _TONE_LABEL["professional"])
    return f"""
You are an AI email drafting assistant.

Write exactly one complete email draft.
Tone: {label}

Rules:
- Plain text only
- No markdown
- No subject line
- Keep it concise and natural
- Avoid repeating the original email word-for-word

Original Email:
{text}

Draft:
""".strip()


def _clean_draft(draft: str) -> str:
    draft = re.sub(r"```.*?```", "", str(draft), flags=re.S)
    draft = re.sub(r"\n{3,}", "\n\n", draft)
    return draft.strip()


def _is_bad_draft(draft: str) -> bool:
    return not draft or len(draft) < 40 or len(draft) > 1200


def generate_qwen_drafts(
    text: str,
    tones: list[str] | None = None,
) -> dict[str, str]:
    if tones is None:
        tones = ["professional"]

    tones = [tone for tone in tones if tone in _FALLBACK_DRAFTS] or ["professional"]

    if not text or len(text.strip()) < 10:
        return {tone: _FALLBACK_DRAFTS[tone] for tone in tones}

    results = {}
    for tone in tones:
        try:
            draft = _clean_draft(generate_response(_build_prompt(text, tone)))
        except Exception:
            draft = ""

        if _is_bad_draft(draft):
            draft = _FALLBACK_DRAFTS[tone]
        results[tone] = draft

    return results


if __name__ == "__main__":
    print(
        generate_qwen_drafts(
            "Can we schedule a project update meeting next week?",
            tones=["casual", "formal", "professional"],
        )
    )
