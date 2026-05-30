"""
Email summarization service with Local BART, Hugging Face API, and fallback.
"""

from __future__ import annotations
import logging
import os
import re
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class SummarizerEngine:
    def __init__(self):
        # Config
        self.model_path = os.getenv("SUMMARY_LOCAL_PATH")
        self.hf_token = (
            os.getenv("SUMMARY_HF_TOKEN")
            or os.getenv("AI_HF_TOKEN")
            or os.getenv("HF_TOKEN")
        )
        self.hf_model_name = (
            os.getenv("SUMMARY_HF_MODEL_NAME")
            or "facebook/bart-large-cnn"
        )

        # State
        self.device: str = self._detect_device()
        self.model_mode: str = "fallback"
        self.tokenizer: Optional[Any] = None
        self.model: Optional[Any] = None
        self.hf_client: Optional[Any] = None
        self.local_attempted = False
        self.hf_attempted = False
        self.last_engine_mode: str = "fallback"

    def _normalize_text(self, value: str | None) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    # --------------------------------------------------
    # DEVICE
    # --------------------------------------------------
    def _detect_device(self) -> str:
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
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
            logger.info("No SUMMARY_LOCAL_PATH configured.")
            return False

        try:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

            logger.info("Loading BART model from %s", self.model_path)
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path, local_files_only=True
            )
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                self.model_path, local_files_only=True
            )
            self.model.to(self.device)
            self.model.eval()
            self.model_mode = "local"
            logger.info("Loaded BART summary model on %s", self.device)
            return True
        except Exception as exc:
            logger.warning("Local summary model load failed: %s", exc)
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
            logger.info("HF token missing. Using fallback mode.")
            return False

        try:
            from huggingface_hub import InferenceClient
            self.hf_client = InferenceClient(
                model=self.hf_model_name, token=self.hf_token
            )
            if self.model_mode != "local":
                self.model_mode = "hf_api"
            logger.info("Initialized HF summarization API: %s", self.hf_model_name)
            return True
        except Exception as exc:
            logger.warning("HF API initialization failed: %s", exc)
            self.hf_client = None
            return False

    # --------------------------------------------------
    # ENGINE SELECTION
    # --------------------------------------------------
    def _ensure_engine(self) -> str:
        if self.load_local():
            return "local"
        if self.load_hf():
            return "hf_api"
        return "fallback"

    # --------------------------------------------------
    # FALLBACK
    # --------------------------------------------------
    def fallback_summary(self, email_text: str) -> str:
        preview = email_text[:300]
        return (
            "Summary service is currently unavailable.\n\n"
            "Preview of email:\n\n"
            f"{preview}..."
        )

    # --------------------------------------------------
    # LOCAL SUMMARY
    # --------------------------------------------------
    def generate_local_summary(self, email_text: str) -> str:
        if not self.tokenizer or not self.model:
            raise RuntimeError("Summary model not loaded.")

        import torch
        inputs = self.tokenizer(
            email_text, return_tensors="pt", max_length=1024, truncation=True
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            summary_ids = self.model.generate(
                **inputs,
                max_length=int(os.getenv("SUMMARY_MAX_LENGTH", 150)),
                min_length=int(os.getenv("SUMMARY_MIN_LENGTH", 40)),
                num_beams=int(os.getenv("SUMMARY_NUM_BEAMS", 4)),
                early_stopping=True,
            )
        return self.tokenizer.decode(summary_ids[0], skip_special_tokens=True).strip()

    # --------------------------------------------------
    # HF SUMMARY
    # --------------------------------------------------
    def generate_hf_summary(self, email_text: str) -> str:
        if not self.hf_client:
            raise RuntimeError("HF summary client not initialized.")

        try:
            response = self.hf_client.summarization(
                email_text,
                generate_parameters={
                    "max_length": int(os.getenv("SUMMARY_MAX_LENGTH", 150)),
                    "min_length": int(os.getenv("SUMMARY_MIN_LENGTH", 40)),
                    "num_beams": int(os.getenv("SUMMARY_NUM_BEAMS", 4)),
                },
            )
        except Exception as exc:
            if "generate_parameters" not in str(exc):
                raise
            logger.info(
                "HF provider rejected summary generation parameters; retrying "
                "with provider defaults."
            )
            response = self.hf_client.summarization(email_text)
        return self._extract_summary_text(response)

    def _extract_summary_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response.strip()

        if isinstance(response, dict):
            value = response.get("generated_text") or response.get("summary_text")
            return str(value or "").strip()

        value = getattr(response, "generated_text", None)
        if value is not None:
            return str(value).strip()

        return str(response or "").strip()

    # --------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------
    def generate_summary(self, email_text: str) -> str:
        email_text = self._normalize_text(email_text)
        if not email_text:
            self.last_engine_mode = "fallback"
            return "Please provide email content to summarize."
        if len(email_text) < 30:
            self.last_engine_mode = "fallback"
            return "Please provide more email content to summarize."

        engine = self._ensure_engine()
        if engine == "local":
            try:
                summary = self.generate_local_summary(email_text)
                self.last_engine_mode = "local"
                return summary
            except Exception as exc:
                logger.warning("Local summarization failed: %s", exc)

        if engine in {"hf_api", "local"}:
            try:
                if not self.hf_client:
                    self.load_hf()
                if self.hf_client:
                    summary = self.generate_hf_summary(email_text)
                    if summary:
                        self.last_engine_mode = "hf_api"
                        return summary
            except Exception as exc:
                logger.warning("HF summarization failed: %s", exc)

        self.last_engine_mode = "fallback"
        return self.fallback_summary(email_text)


# --------------------------------------------------
# TEST
# --------------------------------------------------
if __name__ == "__main__":
    sample = """
    Hello Team,

    We have completed Phase 2 of the migration.
    Testing is scheduled for tomorrow.
    Please review the attached reports and
    share feedback before 5 PM.

    Regards,
    Project Manager
    """
    engine = SummarizerEngine()
    print(engine.generate_summary(sample))
