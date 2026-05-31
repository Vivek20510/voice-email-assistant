from types import SimpleNamespace

from src.services.translation import TranslationEngine


class FakeHFClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def translation(self, text, **kwargs):
        self.calls.append({"text": text, "kwargs": kwargs})
        return self.response


class RejectingGenerateParametersHFClient(FakeHFClient):
    def translation(self, text, **kwargs):
        self.calls.append({"text": text, "kwargs": kwargs})
        if "generate_parameters" in kwargs:
            raise ValueError("model_kwargs are not used: ['generate_parameters']")
        return self.response


def test_hf_translation_uses_translation_task_and_mbart_codes():
    engine = TranslationEngine()
    engine.hf_client = FakeHFClient(
        SimpleNamespace(translation_text="नमस्ते टीम")
    )

    translated = engine.generate_hf_translation("Hello team", "Hindi")

    assert translated == "नमस्ते टीम"
    assert engine.hf_client.calls == [
        {
            "text": "Hello team",
            "kwargs": {
                "src_lang": "en_XX",
                "tgt_lang": "hi_IN",
                "generate_parameters": {
                    "max_length": 512,
                    "num_beams": 4,
                },
            },
        }
    ]


def test_english_translation_returns_text_without_loading_engine(monkeypatch):
    engine = TranslationEngine()
    monkeypatch.setattr(
        engine,
        "ensure_engine",
        lambda: (_ for _ in ()).throw(AssertionError("engine should not load")),
    )

    assert engine.translate("Already English.", "English") == "Already English."


def test_hf_translation_rejects_empty_response():
    engine = TranslationEngine()
    engine.hf_client = FakeHFClient(SimpleNamespace(translation_text=""))

    try:
        engine.generate_hf_translation("Hello team", "Hindi")
    except RuntimeError as exc:
        assert str(exc) == "HF translation returned an empty response."
    else:
        raise AssertionError("Expected an empty translation response to fail.")


def test_hf_translation_retries_without_generate_parameters_when_rejected():
    engine = TranslationEngine()
    engine.hf_client = RejectingGenerateParametersHFClient(
        SimpleNamespace(translation_text="नमस्ते टीम")
    )

    translated = engine.generate_hf_translation("Hello team", "Hindi")

    assert translated == "नमस्ते टीम"
    assert len(engine.hf_client.calls) == 2
    assert "generate_parameters" in engine.hf_client.calls[0]["kwargs"]
    assert engine.hf_client.calls[1]["kwargs"] == {
        "src_lang": "en_XX",
        "tgt_lang": "hi_IN",
    }


def test_hf_translation_defaults_to_hosted_translation_model(monkeypatch):
    monkeypatch.delenv("TRANSLATION_HF_MODEL", raising=False)

    engine = TranslationEngine()

    assert engine.hf_model_name == "facebook/mbart-large-50-many-to-many-mmt"


def test_hf_translation_replaces_unserved_remote_nllb_model(monkeypatch):
    monkeypatch.setenv("TRANSLATION_HF_MODEL", "facebook/nllb-200-distilled-600M")

    engine = TranslationEngine()

    assert engine.hf_model_name == "facebook/mbart-large-50-many-to-many-mmt"
