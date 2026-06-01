"""MMS text-to-speech with local inference and Hugging Face API fallback."""

from __future__ import annotations

import io
import logging
import os
import threading
import wave
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MMS_MODEL_BY_LANGUAGE = {
    "English": "facebook/mms-tts-eng",
    "Hindi": "facebook/mms-tts-hin",
    "Telugu": "facebook/mms-tts-tel",
    "Tamil": "facebook/mms-tts-tam",
    "Kannada": "facebook/mms-tts-kan",
    "Bengali": "facebook/mms-tts-ben",
    "French": "facebook/mms-tts-fra",
    "Spanish": "facebook/mms-tts-spa",
    "German": "facebook/mms-tts-deu",
    "Arabic": "facebook/mms-tts-ara",
}
UNSUPPORTED_MMS_LANGUAGES = {"Chinese", "Japanese"}
UROMAN_FALLBACK_LANGUAGES = {
    "Hindi",
    "Telugu",
    "Tamil",
    "Kannada",
    "Bengali",
    "Arabic",
}
UROMAN_CODE_BY_LANGUAGE = {
    "Hindi": "hin",
    "Telugu": "tel",
    "Tamil": "tam",
    "Kannada": "kan",
    "Bengali": "ben",
    "Arabic": "ara",
}


class UnsupportedTTSLanguageError(ValueError):
    """Raised when no MMS checkpoint is available for the selected language."""


class TTSUnavailableError(RuntimeError):
    """Raised when local and hosted synthesis are both unavailable."""


@dataclass(frozen=True)
class SynthesizedAudio:
    audio: bytes
    content_type: str
    source: str
    model_id: str
    language: str


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _content_type_for_audio(audio: bytes) -> str:
    if audio.startswith(b"RIFF") and audio[8:12] == b"WAVE":
        return "audio/wav"
    if audio.startswith(b"fLaC"):
        return "audio/flac"
    if audio.startswith(b"OggS"):
        return "audio/ogg"
    if audio.startswith(b"ID3") or audio[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
        return "audio/mpeg"
    return "application/octet-stream"


class MMSTTSEngine:
    """Load one MMS language checkpoint at a time and synthesize speech."""

    def __init__(self) -> None:
        self.hf_token = (
            os.getenv("TTS_HF_TOKEN")
            or os.getenv("AI_HF_TOKEN")
            or os.getenv("HF_TOKEN")
        )
        self.cache_dir = os.getenv("TTS_LOCAL_CACHE_PATH") or None
        self.local_enabled = _env_bool("TTS_LOCAL_ENABLED", True)
        self.hf_enabled = _env_bool("TTS_HF_ENABLED", True)
        self.hf_timeout = int(os.getenv("TTS_HF_TIMEOUT_SECONDS", "30"))
        self.seed = int(os.getenv("TTS_SEED", "555"))

        self.device = self._detect_device()
        self._lock = threading.RLock()
        self._active_model_id: str | None = None
        self._tokenizer: Any = None
        self._model: Any = None
        self._hf_client: Any = None
        self._uroman: Any = None

    @staticmethod
    def _detect_device() -> str:
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    @staticmethod
    def model_id_for(language: str) -> str:
        if language in UNSUPPORTED_MMS_LANGUAGES:
            raise UnsupportedTTSLanguageError(
                f"Read aloud is not yet supported for {language}."
            )
        model_id = MMS_MODEL_BY_LANGUAGE.get(language)
        if not model_id:
            raise UnsupportedTTSLanguageError(
                f"Read aloud is not supported for {language}."
            )
        return model_id

    def _load_local(self, model_id: str) -> bool:
        if not self.local_enabled:
            return False
        if self._active_model_id == model_id and self._tokenizer and self._model:
            return True

        try:
            from transformers import VitsModel, VitsTokenizer

            logger.info("Loading local MMS TTS model %s.", model_id)
            tokenizer = VitsTokenizer.from_pretrained(
                model_id,
                cache_dir=self.cache_dir,
            )
            model = VitsModel.from_pretrained(
                model_id,
                cache_dir=self.cache_dir,
            )
            model.to(self.device)
            model.eval()

            self._active_model_id = model_id
            self._tokenizer = tokenizer
            self._model = model
            return True
        except Exception as exc:
            logger.warning("Local MMS TTS model load failed for %s: %s", model_id, exc)
            self._active_model_id = None
            self._tokenizer = None
            self._model = None
            return False

    def _uromanize(self, text: str, language: str) -> str:
        try:
            if self._uroman is None:
                import uroman

                self._uroman = uroman.Uroman()
            return self._uroman.romanize_string(
                text,
                lcode=UROMAN_CODE_BY_LANGUAGE.get(language),
            )
        except Exception as exc:
            raise RuntimeError(
                "uroman preprocessing is required for this language."
            ) from exc

    def _prepare_text(self, text: str, language: str) -> str:
        requires_uroman = language in UROMAN_FALLBACK_LANGUAGES
        if self._tokenizer is not None:
            requires_uroman = bool(
                getattr(self._tokenizer, "is_uroman", requires_uroman)
            )
        return self._uromanize(text, language) if requires_uroman else text

    @staticmethod
    def _wav_bytes(waveform: Any, sampling_rate: int) -> bytes:
        import numpy as np

        samples = waveform.detach().cpu().float().numpy()
        samples = np.clip(samples, -1.0, 1.0)
        pcm = (samples * 32767).astype(np.int16)

        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sampling_rate)
            wav.writeframes(pcm.tobytes())
        return output.getvalue()

    def _synthesize_local(self, text: str, language: str) -> bytes:
        if self._tokenizer is None or self._model is None:
            raise RuntimeError("Local MMS TTS model is not loaded.")

        import torch
        from transformers import set_seed

        prepared_text = self._prepare_text(text, language)
        inputs = self._tokenizer(text=prepared_text, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}

        set_seed(self.seed)
        with torch.no_grad():
            outputs = self._model(**inputs)

        return self._wav_bytes(
            outputs.waveform[0],
            int(self._model.config.sampling_rate),
        )

    def _load_hf_client(self) -> bool:
        if self._hf_client is not None:
            return True
        if not self.hf_enabled or not self.hf_token:
            return False
        if self.hf_token == "replace-with-huggingface-token":
            return False

        try:
            from huggingface_hub import InferenceClient

            self._hf_client = InferenceClient(
                token=self.hf_token,
                timeout=self.hf_timeout,
            )
            return True
        except Exception as exc:
            logger.warning("HF TTS client initialization failed: %s", exc)
            self._hf_client = None
            return False

    def _synthesize_hf(self, text: str, language: str, model_id: str) -> bytes:
        if self._hf_client is None:
            raise RuntimeError("HF TTS client is not initialized.")
        prepared_text = self._prepare_text(text, language)
        return self._hf_client.text_to_speech(prepared_text, model=model_id)

    def synthesize(self, text: str, language: str) -> SynthesizedAudio:
        clean_text = " ".join(str(text or "").split())
        if not clean_text:
            raise ValueError("Text is required.")

        model_id = self.model_id_for(language)
        errors = []

        with self._lock:
            if self._load_local(model_id):
                try:
                    audio = self._synthesize_local(clean_text, language)
                    return SynthesizedAudio(
                        audio=audio,
                        content_type="audio/wav",
                        source="local",
                        model_id=model_id,
                        language=language,
                    )
                except Exception as exc:
                    errors.append(str(exc))
                    logger.warning("Local MMS synthesis failed for %s: %s", model_id, exc)

            if self._load_hf_client():
                try:
                    audio = self._synthesize_hf(clean_text, language, model_id)
                    return SynthesizedAudio(
                        audio=audio,
                        content_type=_content_type_for_audio(audio),
                        source="hf_api",
                        model_id=model_id,
                        language=language,
                    )
                except Exception as exc:
                    errors.append(str(exc))
                    logger.warning("HF MMS synthesis failed for %s: %s", model_id, exc)

        detail = f" Details: {'; '.join(errors)}" if errors else ""
        raise TTSUnavailableError(
            "Read aloud is currently unavailable. Please try again later." + detail
        )


_tts_engine = MMSTTSEngine()


def synthesize_speech(text: str, language: str) -> SynthesizedAudio:
    return _tts_engine.synthesize(text, language)
