import builtins
import sys


def test_transcribe_audio_uses_whisper_model(monkeypatch):
    class DummyModel:
        def transcribe(self, file_path, language=None):
            return {
                "text": "hello world",
                "language": language or "en",
                "segments": [{"id": 0, "text": "hello world"}],
            }

    class DummyWhisper:
        @staticmethod
        def load_model(name):
            assert name == "tiny"
            return DummyModel()

    monkeypatch.setitem(sys.modules, "whisper", DummyWhisper)

    from src.services.voice import transcribe_audio

    result = transcribe_audio("dummy.wav", language="en")
    assert result["text"] == "hello world"
    assert result["language"] == "en"
    assert isinstance(result["segments"], list)
    assert result["segments"][0]["text"] == "hello world"


def test_transcribe_audio_placeholder_when_whisper_missing(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "whisper":
            raise ImportError("No module named whisper")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    from src.services.voice import transcribe_audio

    result = transcribe_audio("dummy.wav", language="fr")
    assert "placeholder" in result["text"].lower()
    assert result["language"] == "fr"
    assert result["segments"] == []
