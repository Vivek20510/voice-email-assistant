"""Qwen reply generation with lazy local, Hugging Face, and text fallbacks."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SUPPORTED_TONES = ("casual", "formal", "professional")

MODEL_PATH = os.getenv("QWEN_REPLY_LOCAL_PATH") or os.getenv("QWEN_LOCAL_PATH")
HF_TOKEN = os.getenv("QWEN_REPLY_HF_TOKEN") or os.getenv("HF_TOKEN")
HF_MODEL_NAME = (
    os.getenv("QWEN_REPLY_HF_MODEL_NAME")
    or os.getenv("HF_MODEL_NAME")
    or "Qwen/Qwen2.5-1.5B-Instruct"
)

REPLY_MODEL_MODE = "fallback"

_device: str | None = None
_tokenizer: Any | None = None
_model: Any | None = None
_hf_client: Any | None = None
_local_attempted = False
_hf_attempted = False

_TONE_LABELS = {
    "casual": "casual and friendly",
    "formal": "formal and polished",
    "professional": "professional and business appropriate",
}


def get_reply_model_mode() -> str:
    return REPLY_MODEL_MODE


def _device_name() -> str:
    global _device

    if _device is None:
        try:
            import torch

            _device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            _device = "cpu"

    return _device


def load_local_model() -> bool:
    """Load a configured local Qwen model once."""
    global _local_attempted, _model, _tokenizer

    if _local_attempted:
        return _model is not None and _tokenizer is not None
    _local_attempted = True

    if not MODEL_PATH:
        logger.info("No local Qwen reply model configured.")
        return False

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        device = _device_name()
        _tokenizer = AutoTokenizer.from_pretrained(
            MODEL_PATH,
            local_files_only=True,
            trust_remote_code=True,
        )
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map="auto" if device == "cuda" else None,
            local_files_only=True,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )
        if device == "cpu":
            _model.to(device)
        _model.eval()
        logger.info("Loaded local Qwen reply model on %s.", device)
        return True
    except Exception as exc:
        logger.warning("Local Qwen reply model load failed: %s", exc)
        _tokenizer = None
        _model = None
        return False


def load_hf_api() -> bool:
    """Initialize the hosted inference client once."""
    global _hf_attempted, _hf_client

    if _hf_attempted:
        return _hf_client is not None
    _hf_attempted = True

    if not HF_TOKEN:
        logger.info("HF token is not configured for reply generation.")
        return False

    try:
        from huggingface_hub import InferenceClient

        _hf_client = InferenceClient(model=HF_MODEL_NAME, token=HF_TOKEN)
        logger.info("Initialized hosted Qwen reply client for %s.", HF_MODEL_NAME)
        return True
    except Exception as exc:
        logger.warning("Hosted Qwen reply client initialization failed: %s", exc)
        _hf_client = None
        return False


def _build_prompt(email_text: str, tone: str) -> str:
    return f"""
You are an AI email reply assistant.

Write exactly ONE complete reply to the original email.

Tone: {_TONE_LABELS[tone]}

Rules:
- Plain text only
- No markdown
- No subject line
- Keep it concise and natural
- Address the request in the original email
- Do not copy the original email word-for-word

Original email:
{email_text}

Reply:
""".strip()


def _clean_reply(reply: str) -> str:
    reply = str(reply or "").strip()
    reply = re.sub(r"```(?:\w+)?\s*(.*?)```", r"\1", reply, flags=re.S)
    reply = re.sub(r"\n{3,}", "\n\n", reply)
    return reply.strip()


def _is_bad_reply(reply: str) -> bool:
    normalized = reply.lower()
    unavailable_markers = (
        "ai service is currently unavailable",
        "basic assistant mode is active",
        "your query:",
    )
    return (
        not reply
        or len(reply) < 40
        or len(reply) > 1200
        or any(marker in normalized for marker in unavailable_markers)
    )


def _fallback_reply(email_text: str, tone: str) -> str:
    topic = re.sub(r"\s+", " ", email_text or "").strip().strip(".")[:500]
    if tone == "casual":
        return (
            "Hi,\n\n"
            f"Thanks for your message about {topic}. "
            "I will review the details and get back to you shortly.\n\n"
            "Best"
        )
    if tone == "formal":
        return (
            "Dear Team,\n\n"
            f"Thank you for your email regarding {topic}. "
            "I will review the details carefully and respond with an update shortly.\n\n"
            "Sincerely"
        )
    return (
        "Hello,\n\n"
        f"Thank you for reaching out regarding {topic}. "
        "I will review the details and follow up with the next steps shortly.\n\n"
        "Best regards"
    )


def generate_local_reply(email_text: str, tone: str) -> str:
    if _tokenizer is None or _model is None:
        raise RuntimeError("Local Qwen reply model is unavailable.")

    import torch

    prompt = _build_prompt(email_text, tone)
    inputs = _tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=1024,
    ).to(_device_name())
    input_length = inputs["input_ids"].shape[1]

    with torch.no_grad():
        outputs = _model.generate(
            **inputs,
            max_new_tokens=250,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            repetition_penalty=1.1,
            pad_token_id=_tokenizer.eos_token_id,
        )

    return _clean_reply(
        _tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
    )


def generate_hf_reply(email_text: str, tone: str) -> str:
    if _hf_client is None:
        raise RuntimeError("Hosted Qwen reply client is unavailable.")

    response = _hf_client.chat_completion(
        messages=[
            {
                "role": "system",
                "content": "Generate concise, useful email replies in plain text.",
            },
            {"role": "user", "content": _build_prompt(email_text, tone)},
        ],
        max_tokens=250,
        temperature=0.7,
    )
    return _clean_reply(response.choices[0].message.content)


def generate_qwen_replies(
    text: str,
    tones: list[str] | None = None,
) -> dict[str, str]:
    """Generate one validated email reply for each requested tone."""
    global REPLY_MODEL_MODE

    requested_tones = tones or list(SUPPORTED_TONES)
    requested_tones = [tone for tone in requested_tones if tone in SUPPORTED_TONES]
    if not requested_tones:
        requested_tones = list(SUPPORTED_TONES)

    email_text = str(text or "").strip()
    if not email_text:
        REPLY_MODEL_MODE = "fallback"
        return {tone: _fallback_reply("your email", tone) for tone in requested_tones}

    local_ready = load_local_model()
    hf_ready = False
    modes_used: set[str] = set()
    replies: dict[str, str] = {}

    for tone in requested_tones:
        reply = ""
        if local_ready:
            try:
                reply = generate_local_reply(email_text, tone)
                if _is_bad_reply(reply):
                    reply = ""
                else:
                    modes_used.add("local")
            except Exception as exc:
                logger.warning("Local Qwen reply generation failed: %s", exc)

        if not reply and not hf_ready:
            hf_ready = load_hf_api()

        if not reply and hf_ready:
            try:
                reply = generate_hf_reply(email_text, tone)
                if _is_bad_reply(reply):
                    reply = ""
                else:
                    modes_used.add("hf_api")
            except Exception as exc:
                logger.warning("Hosted Qwen reply generation failed: %s", exc)

        if not reply:
            reply = _fallback_reply(email_text, tone)
            modes_used.add("fallback")

        replies[tone] = reply

    REPLY_MODEL_MODE = (
        "fallback"
        if "fallback" in modes_used
        else "hf_api"
        if "hf_api" in modes_used
        else "local"
    )
    return replies
