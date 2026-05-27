"""Backward-compatible Qwen reply helpers without eager model loading."""

from __future__ import annotations

from src.services.qwen_draft_service import generate_qwen_drafts


def generate_qwen_replies(
    text: str,
    tones: list[str] | None = None,
) -> dict[str, str]:
    return generate_qwen_drafts(text, tones=tones)
