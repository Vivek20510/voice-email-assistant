from types import SimpleNamespace

from src.services.summary_service import SummarizerEngine


class FakeHFClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def summarization(self, text, **kwargs):
        self.calls.append({"text": text, "kwargs": kwargs})
        return self.response


class RejectingGenerateParametersHFClient(FakeHFClient):
    def summarization(self, text, **kwargs):
        self.calls.append({"text": text, "kwargs": kwargs})
        if "generate_parameters" in kwargs:
            raise ValueError("model_kwargs are not used: ['generate_parameters']")
        return self.response


def test_hf_summary_uses_generate_parameters(monkeypatch):
    monkeypatch.setenv("SUMMARY_MAX_LENGTH", "120")
    monkeypatch.setenv("SUMMARY_MIN_LENGTH", "25")
    monkeypatch.setenv("SUMMARY_NUM_BEAMS", "3")
    engine = SummarizerEngine()
    engine.hf_client = FakeHFClient(SimpleNamespace(generated_text="Roadmap update."))

    summary = engine.generate_hf_summary("Long enough email text to summarize.")

    assert summary == "Roadmap update."
    assert engine.hf_client.calls == [
        {
            "text": "Long enough email text to summarize.",
            "kwargs": {
                "generate_parameters": {
                    "max_length": 120,
                    "min_length": 25,
                    "num_beams": 3,
                }
            },
        }
    ]


def test_hf_summary_retries_without_generate_parameters_when_provider_rejects():
    engine = SummarizerEngine()
    engine.hf_client = RejectingGenerateParametersHFClient(
        SimpleNamespace(generated_text="Provider default summary.")
    )

    summary = engine.generate_hf_summary("Long enough email text to summarize.")

    assert summary == "Provider default summary."
    assert len(engine.hf_client.calls) == 2
    assert "generate_parameters" in engine.hf_client.calls[0]["kwargs"]
    assert engine.hf_client.calls[1]["kwargs"] == {}


def test_hf_summary_extracts_supported_response_shapes():
    engine = SummarizerEngine()

    assert engine._extract_summary_text(" plain summary ") == "plain summary"
    assert (
        engine._extract_summary_text({"generated_text": " generated summary "})
        == "generated summary"
    )
    assert (
        engine._extract_summary_text({"summary_text": " dictionary summary "})
        == "dictionary summary"
    )
    assert (
        engine._extract_summary_text(SimpleNamespace(generated_text=" typed summary "))
        == "typed summary"
    )


def test_generate_summary_falls_through_from_local_to_hf(monkeypatch):
    engine = SummarizerEngine()
    engine.hf_client = FakeHFClient(SimpleNamespace(generated_text="HF summary."))
    monkeypatch.setattr(engine, "load_local", lambda: True)
    monkeypatch.setattr(
        engine,
        "generate_local_summary",
        lambda text: (_ for _ in ()).throw(RuntimeError("local failed")),
    )

    summary = engine.generate_summary(
        "Alice shared the quarterly roadmap and asked for feedback by Friday."
    )

    assert summary == "HF summary."
    assert engine.last_engine_mode == "hf_api"


def test_generate_summary_handles_empty_and_short_text():
    engine = SummarizerEngine()

    assert engine.generate_summary("") == "Please provide email content to summarize."
    assert (
        engine.generate_summary("too short")
        == "Please provide more email content to summarize."
    )
