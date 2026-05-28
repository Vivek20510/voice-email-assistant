"""General AI generation service with local, Hugging Face API, and text fallback."""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MODEL_PATH = os.getenv("AI_LOCAL_PATH") or os.getenv("QWEN_LOCAL_PATH")
HF_TOKEN = os.getenv("AI_HF_TOKEN") or os.getenv("HF_TOKEN")
HF_MODEL_NAME = (
    os.getenv("AI_HF_MODEL_NAME")
    or os.getenv("HF_MODEL_NAME")
    or "Qwen/Qwen2.5-1.5B-Instruct"
)

MODEL_MODE = "fallback"

_device: str | None = None
_tokenizer: Any | None = None
_model: Any | None = None
_hf_client: Any | None = None
_local_attempted = False
_hf_attempted = False


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
    """Load a configured local Qwen model once, if available."""
    global MODEL_MODE, _local_attempted, _model, _tokenizer

    if _local_attempted:
        return MODEL_MODE == "local"
    _local_attempted = True

    if not MODEL_PATH:
        logger.info("No local Qwen model path configured.")
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
        MODEL_MODE = "local"
        logger.info("Loaded local Qwen model on %s.", device)
        return True
    except Exception as exc:
        logger.warning("Local Qwen model load failed: %s", exc)
        _tokenizer = None
        _model = None
        return False


def load_hf_api() -> bool:
    """Initialize Hugging Face hosted inference once, if a token exists."""
    global MODEL_MODE, _hf_attempted, _hf_client

    if _hf_attempted:
        return _hf_client is not None
    _hf_attempted = True

    if not HF_TOKEN:
        logger.info("HF_TOKEN is not configured; using text fallback.")
        return False

    try:
        from huggingface_hub import InferenceClient

        _hf_client = InferenceClient(model=HF_MODEL_NAME, token=HF_TOKEN)
        if MODEL_MODE != "local":
            MODEL_MODE = "hf_api"
        logger.info("Initialized Hugging Face API client for %s.", HF_MODEL_NAME)
        return True
    except Exception as exc:
        logger.warning("Hugging Face API initialization failed: %s", exc)
        _hf_client = None
        return False


def _ensure_engine() -> str:
    if load_local_model():
        return "local"
    if load_hf_api():
        return "hf_api"
    return "fallback"


def build_prompt(user_query: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are an enterprise AI email assistant. "
                "Give concise and professional responses focused on email productivity."
            ),
        },
        {"role": "user", "content": user_query},
    ]

    if _tokenizer is not None and hasattr(_tokenizer, "apply_chat_template"):
        return _tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    return f"System: {messages[0]['content']}\n\n" f"User: {user_query}\n\nAssistant:"


def fallback_response(query: str) -> str:
    return (
        "AI service is currently unavailable.\n\n"
        "Basic assistant mode is active.\n\n"
        f"Your query: {query}"
    )


def generate_local_response(user_query: str) -> str:
    if _tokenizer is None or _model is None:
        raise RuntimeError("Local model is not loaded.")

    import torch

    prompt = build_prompt(user_query)
    device = _device_name()
    inputs = _tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=2048,
    ).to(device)
    input_length = inputs["input_ids"].shape[1]

    with torch.no_grad():
        outputs = _model.generate(
            **inputs,
            max_new_tokens=150,
            temperature=0.4,
            top_p=0.85,
            do_sample=True,
            repetition_penalty=1.15,
            pad_token_id=_tokenizer.eos_token_id,
        )

    generated_tokens = outputs[0][input_length:]
    return _tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()


def generate_hf_response(user_query: str) -> str:
    if _hf_client is None:
        raise RuntimeError("Hugging Face API client is not initialized.")

    response = _hf_client.chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an enterprise AI email assistant. "
                    "Give concise and professional responses focused on email productivity."
                ),
            },
            {
                "role": "user",
                "content": user_query,
            },
        ],
        max_tokens=150,
        temperature=0.4,
    )

    return (
        response
        .choices[0]
        .message
        .content
        .strip()
    )

def generate_response(user_query: str) -> str:
    """Generate text without making app startup depend on any model files."""
    engine = _ensure_engine()

    if engine == "local":
        try:
            return generate_local_response(user_query)
        except Exception as exc:
            logger.exception("Local inference failed: %s", exc)

    if engine in {"hf_api", "local"}:
        try:
            if _hf_client is None:
                load_hf_api()
            if _hf_client is not None:
                return generate_hf_response(user_query)
        except Exception as exc:
            logger.exception("Hugging Face API inference failed: %s", exc)

    return fallback_response(user_query)


if __name__ == "__main__":
    print(generate_response("Summarize today's important emails"))
