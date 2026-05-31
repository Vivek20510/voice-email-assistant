"""
Translation service with:
1. Local NLLB model
2. Hugging Face API fallback
3. Text fallback
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from dotenv import load_dotenv
from src.services.preferences import DEFAULT_LANGUAGE, normalize_language

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_HF_TRANSLATION_MODEL = "facebook/mbart-large-50-many-to-many-mmt"
UNSUPPORTED_HOSTED_TRANSLATION_MODELS = {
    "facebook/nllb-200-distilled-600M",
}


class TranslationEngine:
    def __init__(self):
        # --------------------------------------------------
        # CONFIG
        # --------------------------------------------------

        self.model_path = os.getenv("NLLB_LOCAL_PATH")

        self.hf_token = (
            os.getenv("TRANSLATION_HF_TOKEN")
            or os.getenv("AI_HF_TOKEN")
            or os.getenv("HF_TOKEN")
        )

        configured_hf_model = (os.getenv("TRANSLATION_HF_MODEL") or "").strip()
        if configured_hf_model in UNSUPPORTED_HOSTED_TRANSLATION_MODELS:
            logger.warning(
                "%s is not served by HF-Inference; using %s for hosted translation.",
                configured_hf_model,
                DEFAULT_HF_TRANSLATION_MODEL,
            )
            configured_hf_model = ""

        self.hf_model_name = configured_hf_model or DEFAULT_HF_TRANSLATION_MODEL

        self.max_length = int(
            os.getenv("TRANSLATION_MAX_LENGTH", 512)
        )

        self.num_beams = int(
            os.getenv("TRANSLATION_NUM_BEAMS", 4)
        )

        # --------------------------------------------------
        # STATE
        # --------------------------------------------------

        self.device = self._detect_device()
        self.model_mode = "fallback"

        self.tokenizer: Optional[Any] = None
        self.model: Optional[Any] = None
        self.hf_client: Optional[Any] = None

        self.local_attempted = False
        self.hf_attempted = False

        # --------------------------------------------------
        # LANGUAGES
        # --------------------------------------------------

        self.local_lang_map = {
            "English": "eng_Latn",
            "Hindi": "hin_Deva",
            "Telugu": "tel_Telu",
            "Tamil": "tam_Taml",
            "Kannada": "kan_Knda",
            "Bengali": "ben_Beng",
            "French": "fra_Latn",
            "Spanish": "spa_Latn",
            "German": "deu_Latn",
            "Arabic": "arb_Arab",
            "Chinese": "zho_Hans",
            "Japanese": "jpn_Jpan",
        }
        self.hf_lang_map = {
            "English": "en_XX",
            "Hindi": "hi_IN",
            "Telugu": "te_IN",
            "Tamil": "ta_IN",
            "Kannada": "kn_IN",
            "Bengali": "bn_IN",
            "French": "fr_XX",
            "Spanish": "es_XX",
            "German": "de_DE",
            "Arabic": "ar_AR",
            "Chinese": "zh_CN",
            "Japanese": "ja_XX",
        }

    # --------------------------------------------------
    # DEVICE
    # --------------------------------------------------

    def _detect_device(self) -> str:
        try:
            import torch

            return (
                "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )
        except Exception:
            return "cpu"

    # --------------------------------------------------
    # LOCAL MODEL
    # --------------------------------------------------

    def load_local(self) -> bool:
        if self.local_attempted:
            return self.model_mode == "local"

        self.local_attempted = True

        if not self.model_path:
            logger.info(
                "No NLLB_LOCAL_PATH configured."
            )
            return False

        try:
            from transformers import (
                AutoTokenizer,
                AutoModelForSeq2SeqLM,
            )

            logger.info(
                "Loading NLLB model from %s",
                self.model_path,
            )

            self.tokenizer = (
                AutoTokenizer.from_pretrained(
                    self.model_path,
                    local_files_only=True,
                )
            )

            self.model = (
                AutoModelForSeq2SeqLM.from_pretrained(
                    self.model_path,
                    local_files_only=True,
                )
            )

            self.model.to(self.device)
            self.model.eval()

            self.model_mode = "local"

            logger.info(
                "Loaded NLLB model on %s",
                self.device,
            )

            return True

        except Exception as exc:
            logger.exception(
                "Local translation model load failed: %s",
                exc,
            )

            self.tokenizer = None
            self.model = None

            return False

    # --------------------------------------------------
    # HF API
    # --------------------------------------------------

    def load_hf(self) -> bool:
        if self.hf_attempted:
            return self.hf_client is not None

        self.hf_attempted = True

        if not self.hf_token:
            logger.info(
                "Translation HF token not configured."
            )
            return False

        if not self.hf_model_name or not self.hf_model_name.strip():
            logger.error("TRANSLATION_HF_MODEL must be a non-empty translation model ID.")
            return False

        try:
            from huggingface_hub import (
                InferenceClient,
            )

            self.hf_client = InferenceClient(
                model=self.hf_model_name,
                token=self.hf_token,
                provider="hf-inference",
            )

            if self.model_mode != "local":
                self.model_mode = "hf_api"

            logger.info(
                "Initialized HF Translation API (%s)",
                self.hf_model_name,
            )

            return True

        except Exception as exc:
            logger.exception(
                "HF Translation API init failed: %s",
                exc,
            )

            self.hf_client = None

            return False

    # --------------------------------------------------
    # ENGINE
    # --------------------------------------------------

    def ensure_engine(self) -> str:
        if self.load_local():
            return "local"

        if self.load_hf():
            return "hf_api"

        return "fallback"

    # --------------------------------------------------
    # LOCAL TRANSLATION
    # --------------------------------------------------

    def generate_local_translation(
        self,
        text: str,
        target_language: str,
    ) -> str:

        if (
            self.tokenizer is None
            or self.model is None
        ):
            raise RuntimeError(
                "Translation model not loaded."
            )

        target_lang_code = self.local_lang_map.get(
            target_language,
            "eng_Latn",
        )
        self.tokenizer.src_lang = self.local_lang_map[DEFAULT_LANGUAGE]

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=512,
        )

        inputs = {
            k: v.to(self.device)
            for k, v in inputs.items()
        }

        translated_tokens = self.model.generate(
            **inputs,
            forced_bos_token_id=
            self.tokenizer.convert_tokens_to_ids(
                target_lang_code
            ),
            max_length=self.max_length,
            num_beams=self.num_beams,
            early_stopping=True,
        )

        return self.tokenizer.batch_decode(
            translated_tokens,
            skip_special_tokens=True,
        )[0].strip()

    # --------------------------------------------------
    # HF TRANSLATION
    # --------------------------------------------------

    def generate_hf_translation(
        self,
        text: str,
        target_language: str,
    ) -> str:

        if self.hf_client is None:
            raise RuntimeError(
                "HF Translation client not initialized."
            )

        translation_kwargs = {
            "src_lang": self.hf_lang_map[DEFAULT_LANGUAGE],
            "tgt_lang": self.hf_lang_map[target_language],
        }
        try:
            response = self.hf_client.translation(
                text,
                **translation_kwargs,
                generate_parameters={
                    "max_length": self.max_length,
                    "num_beams": self.num_beams,
                },
            )
        except Exception as exc:
            if "generate_parameters" not in str(exc):
                raise
            logger.info(
                "HF provider rejected translation generation parameters; retrying "
                "with provider defaults."
            )
            response = self.hf_client.translation(text, **translation_kwargs)

        if isinstance(response, str):
            translated_text = response.strip()
        elif isinstance(response, dict):
            translated_text = str(response.get("translation_text", "")).strip()
        else:
            translated_text = str(getattr(response, "translation_text", "")).strip()

        if not translated_text:
            raise RuntimeError("HF translation returned an empty response.")

        return translated_text

    # --------------------------------------------------
    # FALLBACK
    # --------------------------------------------------

    def fallback_translation(
        self,
        text: str,
    ) -> str:

        logger.warning(
            "Translation fallback activated."
        )

        return text

    # --------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------

    def translate(
        self,
        text: str,
        target_language: str = "English",
    ) -> str:

        if not text or not text.strip():
            return ""

        target_language = normalize_language(target_language)
        if target_language == DEFAULT_LANGUAGE:
            return text

        engine = self.ensure_engine()

        if engine == "local":
            try:
                return self.generate_local_translation(
                    text,
                    target_language,
                )
            except Exception as exc:
                logger.exception(
                    "Local translation failed: %s",
                    exc,
                )

        if engine in {"local", "hf_api"}:
            try:
                if self.hf_client is None:
                    self.load_hf()

                if self.hf_client:
                    return self.generate_hf_translation(
                        text,
                        target_language,
                    )

            except Exception as exc:
                logger.exception(
                    "HF translation failed: %s",
                    exc,
                )

        return self.fallback_translation(text)


# --------------------------------------------------
# SINGLETON INSTANCE
# --------------------------------------------------

_translation_engine = TranslationEngine()


def translate_text(
    text: str,
    target_language: str = "English",
) -> str:
    return _translation_engine.translate(
        text,
        target_language,
    )


def get_translation_engine() -> str:
    return _translation_engine.model_mode


# --------------------------------------------------
# TEST
# --------------------------------------------------

if __name__ == "__main__":
    sample = (
        "Hello Team, the migration "
        "has been completed successfully."
    )

    print(
        translate_text(
            sample,
            "Hindi",
        )
    )
