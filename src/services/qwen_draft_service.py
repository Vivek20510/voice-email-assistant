"""
qwen_draft_service.py

Email Draft Generator
Architecture:
Local Qwen -> HF API -> Static Fallback
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

MODEL_PATH = (
    os.getenv("QWEN_DRAFT_LOCAL_PATH")
    or os.getenv("QWEN_LOCAL_PATH")
)

HF_TOKEN = os.getenv("QWEN_DRAFT_HF_TOKEN") or os.getenv("HF_TOKEN")
HF_MODEL_NAME = (
    os.getenv("QWEN_DRAFT_HF_MODEL_NAME")
    or os.getenv("HF_MODEL_NAME")
    or "Qwen/Qwen2.5-1.5B-Instruct"
)

DRAFT_MODEL_MODE = "fallback"


def get_draft_model_mode() -> str:
    return DRAFT_MODEL_MODE

# --------------------------------------------------
# FALLBACK DRAFTS
# --------------------------------------------------

_FALLBACK_DRAFTS = {
    "casual": (
        "Hi,\n\n"
        "I hope you're doing well. "
        "I wanted to reach out regarding your email. "
        "Please let me know a convenient time to discuss further.\n\n"
        "Best regards"
    ),
    "formal": (
        "Dear Sir/Madam,\n\n"
        "Thank you for your email. "
        "I appreciate your message and will review the details carefully. "
        "I will get back to you shortly with an update.\n\n"
        "Sincerely"
    ),
    "professional": (
        "Hello,\n\n"
        "Thank you for reaching out. "
        "I have reviewed your message and will follow up with the necessary information shortly.\n\n"
        "Best regards"
    ),
}

# --------------------------------------------------
# GLOBALS
# --------------------------------------------------

_device: str | None = None
_tokenizer: Any | None = None
_model: Any | None = None
_hf_client: Any | None = None

_local_attempted = False
_hf_attempted = False

# --------------------------------------------------
# DEVICE
# --------------------------------------------------

def _device_name() -> str:
    global _device

    if _device is None:
        try:
            import torch
            _device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            _device = "cpu"

    return _device

# --------------------------------------------------
# LOCAL MODEL
# --------------------------------------------------

def load_local_model() -> bool:
    global DRAFT_MODEL_MODE
    global _local_attempted
    global _tokenizer
    global _model

    if _local_attempted:
        return _model is not None

    _local_attempted = True

    if not MODEL_PATH:
        logger.info("No local draft model configured")
        return False

    try:
        import torch
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
        )

        device = _device_name()

        logger.info("Loading local draft model...")

        _tokenizer = AutoTokenizer.from_pretrained(
            MODEL_PATH,
            local_files_only=True,
            trust_remote_code=True,
        )

        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            torch_dtype=(
                torch.float16
                if device == "cuda"
                else torch.float32
            ),
            device_map="auto" if device == "cuda" else None,
            local_files_only=True,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )

        if device == "cpu":
            _model.to(device)

        _model.eval()

        logger.info(
            "Draft model loaded on %s",
            device,
        )

        DRAFT_MODEL_MODE = "local"

        return True

    except Exception as exc:
        logger.exception(
            "Draft model load failed: %s",
            exc,
        )

        _tokenizer = None
        _model = None

        return False

# --------------------------------------------------
# HF API
# --------------------------------------------------

def load_hf_api() -> bool:
    global DRAFT_MODEL_MODE
    global _hf_attempted
    global _hf_client

    if _hf_attempted:
        return _hf_client is not None

    _hf_attempted = True

    if not HF_TOKEN:
        logger.info("HF_TOKEN not configured")
        return False

    try:
        from huggingface_hub import InferenceClient

        _hf_client = InferenceClient(
            model=HF_MODEL_NAME,
            token=HF_TOKEN,
        )

        logger.info(
            "HF Draft API initialized"
        )

        if DRAFT_MODEL_MODE != "local":
            DRAFT_MODEL_MODE = "hf_api"

        return True

    except Exception as exc:
        logger.exception(
            "HF init failed: %s",
            exc,
        )

        return False

# --------------------------------------------------
# PROMPTS
# --------------------------------------------------

_TONE_LABEL = {
    "casual": "casual and friendly",
    "formal": "formal and polished",
    "professional":
        "professional and business appropriate",
}

def _build_prompt(
    email_text: str,
    tone: str,
) -> str:

    tone_label = _TONE_LABEL.get(
        tone,
        "professional and business appropriate",
    )

    return f"""
You are an AI email drafting assistant.

Write exactly ONE complete email draft.

Tone: {tone_label}

Rules:
- Plain text only
- No markdown
- No subject line
- No headers
- Keep it concise
- Professional language

User request or email subject:
{email_text}

Draft:
""".strip()

# --------------------------------------------------
# CLEANING
# --------------------------------------------------

def _clean_draft(
    draft: str,
) -> str:

    draft = str(draft).strip()

    draft = re.sub(
        r"```.*?```",
        "",
        draft,
        flags=re.S,
    )

    draft = re.sub(
        r"\n{3,}",
        "\n\n",
        draft,
    )

    return draft.strip()


def _fallback_draft(text: str, tone: str) -> str:
    topic = re.sub(r"\s+", " ", text or "").strip().strip(".")
    if not topic:
        return _FALLBACK_DRAFTS.get(tone, _FALLBACK_DRAFTS["professional"])

    greeting = "Hi" if tone == "casual" else "Dear Team" if tone == "formal" else "Hello"
    closing = "Best" if tone == "casual" else "Sincerely" if tone == "formal" else "Best regards"
    return (
        f"{greeting},\n\n"
        f"I am writing regarding {topic}. "
        "Please review the details and let me know if you have any questions or need any additional information. "
        "I would be happy to discuss the next steps at your convenience.\n\n"
        f"{closing}"
    )

def _is_bad_draft(
    draft: str,
) -> bool:

    if not draft:
        return True

    if len(draft) < 40:
        return True

    if len(draft) > 1200:
        return True

    return False

# --------------------------------------------------
# LOCAL GENERATION
# --------------------------------------------------

def generate_local_draft(
    text: str,
    tone: str,
) -> str:

    if _model is None or _tokenizer is None:
        raise RuntimeError(
            "Local model unavailable"
        )

    import torch

    prompt = _build_prompt(
        text,
        tone,
    )

    device = _device_name()

    inputs = _tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=1024,
    ).to(device)

    input_len = (
        inputs["input_ids"]
        .shape[1]
    )

    with torch.no_grad():

        outputs = _model.generate(
            **inputs,
            max_new_tokens=250,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            repetition_penalty=1.1,
            pad_token_id=
            _tokenizer.eos_token_id,
        )

    generated_tokens = outputs[0][input_len:]

    draft = _tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True,
    )

    return _clean_draft(draft)

# --------------------------------------------------
# HF GENERATION
# --------------------------------------------------

def generate_hf_draft(
    text: str,
    tone: str,
) -> str:

    if _hf_client is None:
        raise RuntimeError(
            "HF unavailable"
        )

    response = _hf_client.chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional email drafting assistant. "
                    "Generate clear, concise, business-quality email drafts."
                ),
            },
            {
                "role": "user",
                "content": _build_prompt(
                    text,
                    tone,
                ),
            },
        ],
        max_tokens=250,
        temperature=0.7,
    )

    draft = (
        response
        .choices[0]
        .message
        .content
    )

    return _clean_draft(draft)

# --------------------------------------------------
# MAIN API
# --------------------------------------------------

def generate_qwen_drafts(
    text: str,
    tones: list[str] | None = None,
) -> dict[str, str]:

    if tones is None:
        tones = ["professional"]

    if not text or not text.strip():
        return {
            tone: _FALLBACK_DRAFTS.get(
                tone,
                _FALLBACK_DRAFTS[
                    "professional"
                ],
            )
            for tone in tones
        }

    results = {}

    local_ready = load_local_model()
    hf_ready = load_hf_api()

    for tone in tones:

        draft = None

        # LOCAL
        if local_ready:

            try:
                draft = generate_local_draft(
                    text,
                    tone,
                )

                if _is_bad_draft(
                    draft
                ):
                    draft = None

            except Exception as exc:

                logger.exception(
                    "Local draft failed: %s",
                    exc,
                )

        # HF
        if draft is None and hf_ready:

            try:
                draft = generate_hf_draft(
                    text,
                    tone,
                )

                if _is_bad_draft(
                    draft
                ):
                    draft = None

            except Exception as exc:

                logger.exception(
                    "HF draft failed: %s",
                    exc,
                )

        # FALLBACK
        if draft is None:
            draft = _fallback_draft(text, tone)

        results[tone] = draft

    return results
