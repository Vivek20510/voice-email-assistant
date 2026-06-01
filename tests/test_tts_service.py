import sys
from types import SimpleNamespace

import pytest

from src.services.tts import (
    MMSTTSEngine,
    TTSUnavailableError,
    UnsupportedTTSLanguageError,
)


def test_mms_model_mapping_and_unsupported_languages():
    assert MMSTTSEngine.model_id_for("English") == "facebook/mms-tts-eng"
    assert MMSTTSEngine.model_id_for("Hindi") == "facebook/mms-tts-hin"

    with pytest.raises(UnsupportedTTSLanguageError, match="not yet supported"):
        MMSTTSEngine.model_id_for("Chinese")


def test_local_loader_reuses_active_model_and_replaces_language(monkeypatch):
    loaded = []

    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, model_id, **_kwargs):
            loaded.append(("tokenizer", model_id))
            return SimpleNamespace(is_uroman=False)

    class FakeModel:
        @classmethod
        def from_pretrained(cls, model_id, **_kwargs):
            loaded.append(("model", model_id))
            return cls()

        def to(self, _device):
            return self

        def eval(self):
            return self

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(VitsModel=FakeModel, VitsTokenizer=FakeTokenizer),
    )
    engine = MMSTTSEngine()

    assert engine._load_local("facebook/mms-tts-eng") is True
    assert engine._load_local("facebook/mms-tts-eng") is True
    assert engine._load_local("facebook/mms-tts-hin") is True
    assert loaded == [
        ("tokenizer", "facebook/mms-tts-eng"),
        ("model", "facebook/mms-tts-eng"),
        ("tokenizer", "facebook/mms-tts-hin"),
        ("model", "facebook/mms-tts-hin"),
    ]


def test_prepare_text_uses_cached_uroman_for_required_language():
    calls = []

    class FakeUroman:
        def romanize_string(self, text, lcode=None):
            calls.append((text, lcode))
            return "namaste"

    engine = MMSTTSEngine()
    engine._tokenizer = SimpleNamespace(is_uroman=True)
    engine._uroman = FakeUroman()

    assert engine._prepare_text("नमस्ते", "Hindi") == "namaste"
    assert calls == [("नमस्ते", "hin")]


def test_synthesize_prefers_local_then_falls_back_to_hf(monkeypatch):
    engine = MMSTTSEngine()
    monkeypatch.setattr(engine, "_load_local", lambda _model_id: True)
    monkeypatch.setattr(engine, "_synthesize_local", lambda _text, _language: b"RIFF....WAVE")
    monkeypatch.setattr(engine, "_load_hf_client", lambda: pytest.fail("HF should not load"))

    local = engine.synthesize("Hello", "English")
    assert local.source == "local"
    assert local.content_type == "audio/wav"

    monkeypatch.setattr(
        engine,
        "_synthesize_local",
        lambda _text, _language: (_ for _ in ()).throw(RuntimeError("local failed")),
    )
    monkeypatch.setattr(engine, "_load_hf_client", lambda: True)
    monkeypatch.setattr(engine, "_synthesize_hf", lambda *_args: b"fLaCaudio")

    hosted = engine.synthesize("Hello", "English")
    assert hosted.source == "hf_api"
    assert hosted.content_type == "audio/flac"


def test_synthesize_reports_unavailable_after_both_layers_fail(monkeypatch):
    engine = MMSTTSEngine()
    monkeypatch.setattr(engine, "_load_local", lambda _model_id: False)
    monkeypatch.setattr(engine, "_load_hf_client", lambda: False)

    with pytest.raises(TTSUnavailableError, match="currently unavailable"):
        engine.synthesize("Hello", "English")

