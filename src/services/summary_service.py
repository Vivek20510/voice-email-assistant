"""Email summary service with lazy local model loading and AI fallback."""

from __future__ import annotations

import logging
import os
from typing import Any

from src.services.ai_service import generate_response

logger = logging.getLogger(__name__)

MODEL_PATH = os.getenv("SUMMARY_LOCAL_PATH")
DEVICE = "cpu"

_tokenizer: Any | None = None
_model: Any | None = None
_load_attempted = False

SUMMARY_FALLBACK = "Summary is temporarily unavailable. Please review the message."


def _load_local_summary_model() -> bool:
    global DEVICE, _load_attempted, _model, _tokenizer

    if _load_attempted:
        return _tokenizer is not None and _model is not None
    _load_attempted = True

    if not MODEL_PATH:
        return False

    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        _tokenizer = AutoTokenizer.from_pretrained(
            MODEL_PATH,
            local_files_only=True,
        )
        _model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_PATH,
            local_files_only=True,
        ).to(DEVICE)
        _model.eval()
        return True
    except Exception as exc:
        logger.warning("Local summary model load failed: %s", exc)
        _tokenizer = None
        _model = None
        return False


def _generate_local_summary(email_text: str) -> str:
    if _tokenizer is None or _model is None:
        raise RuntimeError("Summary model is not loaded.")

    import torch

    inputs = _tokenizer(
        email_text,
        return_tensors="pt",
        max_length=1024,
        truncation=True,
    ).to(DEVICE)

    with torch.no_grad():
        summary_ids = _model.generate(
            **inputs,
            max_length=150,
            min_length=30,
            num_beams=4,
            early_stopping=True,
        )

    return _tokenizer.decode(summary_ids[0], skip_special_tokens=True).strip()


def generate_summary(email_text: str) -> str:
    if not email_text or len(email_text.strip()) < 30:
        return "Please provide more email content to summarize."

    if _load_local_summary_model():
        try:
            summary = _generate_local_summary(email_text)
            if summary:
                return summary
        except Exception as exc:
            logger.exception("Local summary generation failed: %s", exc)

    prompt = f"""
You are an email assistant.

Summarize this email clearly and professionally in 2-4 short bullet points.

Email:
{email_text}
""".strip()

    try:
        summary = generate_response(prompt).strip()
        return summary or SUMMARY_FALLBACK
    except Exception as exc:
        logger.exception("AI summary generation failed: %s", exc)
        return SUMMARY_FALLBACK
