"""Translation service with lazy local NLLB loading and safe text fallback."""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TRANSLATION_PATH = os.getenv("NLLB_LOCAL_PATH")
DEVICE = "cpu"

_tokenizer: Any | None = None
_model: Any | None = None
_load_attempted = False

LANG_MAP = {
    "English": "eng_Latn",
    "Telugu": "tel_Telu",
    "Hindi": "hin_Deva",
    "Tamil": "tam_Taml",
    "Kannada": "kan_Knda",
    "French": "fra_Latn",
    "Spanish": "spa_Latn",
    "German": "deu_Latn",
    "Arabic": "arb_Arab",
    "Chinese": "zho_Hans",
    "Japanese": "jpn_Jpan",
}


def _load_translation_model() -> bool:
    global DEVICE, _load_attempted, _model, _tokenizer

    if _load_attempted:
        return _tokenizer is not None and _model is not None
    _load_attempted = True

    if not TRANSLATION_PATH:
        return False

    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        _tokenizer = AutoTokenizer.from_pretrained(
            TRANSLATION_PATH,
            local_files_only=True,
        )
        _model = AutoModelForSeq2SeqLM.from_pretrained(
            TRANSLATION_PATH,
            local_files_only=True,
        ).to(DEVICE)
        _model.eval()
        return True
    except Exception as exc:
        logger.warning("Translation model load failed: %s", exc)
        _tokenizer = None
        _model = None
        return False


def translate_text(text: str, target_language: str = "English") -> str:
    if not text or not text.strip():
        return ""

    if target_language == "English":
        return text

    if not _load_translation_model():
        return text

    try:
        target_lang_code = LANG_MAP.get(target_language, "eng_Latn")
        inputs = _tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        ).to(DEVICE)
        translated_tokens = _model.generate(
            **inputs,
            forced_bos_token_id=_tokenizer.convert_tokens_to_ids(target_lang_code),
            max_length=512,
            num_beams=4,
            early_stopping=True,
        )
        return _tokenizer.batch_decode(
            translated_tokens,
            skip_special_tokens=True,
        )[0]
    except Exception as exc:
        logger.exception("Translation failed: %s", exc)
        return text
