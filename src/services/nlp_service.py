"""NLP helpers for summaries and reply suggestions."""

from __future__ import annotations

import os
import re
from typing import Any

import requests

BART_SUMMARIZATION_MODEL = "facebook/bart-large-cnn"
HF_INFERENCE_URL = (
    f"https://api-inference.huggingface.co/models/{BART_SUMMARIZATION_MODEL}"
)
HF_REQUEST_TIMEOUT_SECONDS = 30
MAX_SUMMARY_INPUT_CHARS = 6000
SUMMARY_FALLBACK = (
    "Summary is temporarily unavailable. Please review the message body below."
)
SUMMARY_LOADING_FALLBACK = "Summary model is warming up. Please try again in a moment."


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def build_email_summary_input(
    text: str | None = None,
    subject: str | None = None,
    sender: str | None = None,
    body: str | None = None,
) -> str:
    """Create a compact summarization prompt from plain text or email fields."""
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


def _extract_summary(payload: Any) -> str | None:
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            return _normalize_text(first.get("summary_text"))
    if isinstance(payload, dict):
        return _normalize_text(payload.get("summary_text"))
    return None


def _is_hf_cold_start_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False

    error = _normalize_text(str(payload.get("error") or ""))
    if "loading" in error.lower() or "currently loading" in error.lower():
        return True
    return isinstance(payload.get("estimated_time"), (int, float))


def summarize_text(
    text: str | None = None,
    *,
    subject: str | None = None,
    sender: str | None = None,
    body: str | None = None,
) -> str:
    """Summarize text or email fields with hosted BART inference."""
    summary_input = build_email_summary_input(
        text=text,
        subject=subject,
        sender=sender,
        body=body,
    )
    if not summary_input:
        return SUMMARY_FALLBACK

    token = os.getenv("HF_TOKEN")
    if not token:
        return SUMMARY_FALLBACK

    try:
        response = requests.post(
            HF_INFERENCE_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "inputs": summary_input,
                "parameters": {
                    "max_length": 130,
                    "min_length": 30,
                    "do_sample": False,
                },
                "options": {"wait_for_model": True},
            },
            timeout=HF_REQUEST_TIMEOUT_SECONDS,
        )
        payload = response.json()
        if response.status_code == 503 and _is_hf_cold_start_payload(payload):
            return SUMMARY_LOADING_FALLBACK

        response.raise_for_status()
        if _is_hf_cold_start_payload(payload):
            return SUMMARY_LOADING_FALLBACK

        summary = _extract_summary(payload)
        return summary or SUMMARY_FALLBACK
    except (requests.RequestException, ValueError, TypeError):
        return SUMMARY_FALLBACK


def suggest_replies(text: str) -> list[str]:
    """Return placeholder reply suggestions."""
    return [
        "Thanks for the update! I'll follow up soon.",
        "Can you share more details so I can help?",
    ]
