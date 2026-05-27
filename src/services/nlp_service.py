"""

Unified NLP Service:

- AI-powered summarization

- Tone-aware reply suggestions

- Robust fallbacks for production use

"""

from __future__ import annotations


import re

import logging

from typing import Any

# ✅ Core AI service

from src.services.ai_service import generate_response, MODEL_MODE

logger = logging.getLogger(__name__)


# =========================================================

# CONFIG

# =========================================================


MAX_SUMMARY_INPUT_CHARS = 6000


SUMMARY_FALLBACK = (
    "Summary is temporarily unavailable. Please review the message below."
)


# ✅ Tone-based fallback replies

_FALLBACK_REPLIES: dict[str, str] = {
    "casual": "Hey, got your message! I'll take a look and get back to you soon.",
    "formal": "Thank you for your correspondence. I will review this and respond shortly.",
    "professional": "Thank you for reaching out. I will review this and follow up shortly.",
}


SUPPORTED_TONES = ["casual", "formal", "professional"]


# =========================================================

# HELPERS

# =========================================================


def _normalize_text(value: str | None) -> str:

    return re.sub(r"\s+", " ", value or "").strip()


def build_email_summary_input(
    text: str | None = None,
    subject: str | None = None,
    sender: str | None = None,
    body: str | None = None,
) -> str:

    text = _normalize_text(text)

    subject = _normalize_text(subject)

    sender = _normalize_text(sender)

    body = _normalize_text(body)

    if text:

        summary_input = text

    else:

        parts = []

        if subject:

            parts.append(f"Subject: {subject}")

        if sender:

            parts.append(f"Sender: {sender}")

        if body:

            parts.append(f"Body: {body}")

        summary_input = " ".join(parts)

    return summary_input[:MAX_SUMMARY_INPUT_CHARS].strip()


# =========================================================

# SUMMARIZATION (AI-powered)

# =========================================================


def summarize_text(
    text: str | None = None,
    *,
    subject: str | None = None,
    sender: str | None = None,
    body: str | None = None,
) -> str:
    """

    Generate AI summary using Qwen (via generate_response).

    Falls back safely if AI fails.

    """

    summary_input = build_email_summary_input(
        text=text,
        subject=subject,
        sender=sender,
        body=body,
    )

    if not summary_input:

        return SUMMARY_FALLBACK

    prompt = f"""

You are an email assistant.


 

Summarize this email in a clear and professional way.

Use bullet points if needed.


 

Email:

{summary_input}

"""

    try:

        response = generate_response(prompt)

        if response and response.strip():

            return response.strip()

    except Exception as exc:

        logger.exception("Summarization failed: %s", exc)

    return SUMMARY_FALLBACK


# =========================================================

# SMART REPLY SUGGESTIONS (AI + STRUCTURE)

# =========================================================


def suggest_replies(
    text: str,
    tones: list[str] | None = None,
) -> dict[str, str]:
    """

    Generate AI replies for each tone.

    Always returns valid structured output.




    Example:

    {

        "casual": "...",

        "formal": "...",

        "professional": "..."

    }

    """

    # ✅ Normalize tones

    if tones is None:

        tones = SUPPORTED_TONES

    tones = [t for t in tones if t in SUPPORTED_TONES] or SUPPORTED_TONES

    # ✅ Empty input → fallback immediately

    if not text or not text.strip():

        return {t: _FALLBACK_REPLIES[t] for t in tones}

    prompt = f"""

You are an AI email assistant.


 

Generate ONE reply per tone for the following email.


 

Tones:

- casual

- formal

- professional


 

Return clearly separated responses.


 

Email:

{text}

"""

    try:

        ai_output = generate_response(prompt)

        if not ai_output:

            raise ValueError("Empty AI response")

        # ✅ Simple parsing strategy

        lines = [line.strip() for line in ai_output.split("\n") if line.strip()]

        results: dict[str, str] = {}

        for i, tone in enumerate(tones):

            if i < len(lines):

                results[tone] = lines[i]

            else:

                results[tone] = _FALLBACK_REPLIES[tone]

        return results

    except Exception as exc:

        logger.exception("suggest_replies failed: %s", exc)

        return {t: _FALLBACK_REPLIES[t] for t in tones}


# =========================================================

# GENERAL PURPOSE AI (used everywhere)

# =========================================================


def generate_ai_response(query: str) -> str:
    """

    Wrapper around core AI for consistency.

    """

    try:

        return generate_response(query) or ""

    except Exception as exc:

        logger.exception("AI response failed: %s", exc)

        return "⚠️ AI service is currently unavailable."
