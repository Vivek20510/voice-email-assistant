import sys

from src.services import voice


def _reset_stt_globals(monkeypatch):
    monkeypatch.setattr(voice, "_local_attempted", False)
    monkeypatch.setattr(voice, "_hf_attempted", False)
    monkeypatch.setattr(voice, "_whisper_model", None)
    monkeypatch.setattr(voice, "_hf_client", None)
    monkeypatch.setattr(voice, "_convert_to_wav", lambda _path: None)


def test_transcribe_audio_uses_local_whisper(monkeypatch):
    _reset_stt_globals(monkeypatch)
    monkeypatch.setattr(voice, "_load_local_whisper", lambda: True)
    monkeypatch.setattr(
        voice,
        "_transcribe_local",
        lambda _path: ("hello world", 0.05),
    )

    result = voice.transcribe_audio("dummy.wav", language="en")

    assert result == {
        "success": True,
        "text": "hello world",
        "language": "en",
        "segments": [],
        "source": "local",
        "error": None,
    }


def test_transcribe_audio_uses_hf_when_local_whisper_is_unavailable(monkeypatch):
    _reset_stt_globals(monkeypatch)
    monkeypatch.setattr(voice, "_load_local_whisper", lambda: False)
    monkeypatch.setattr(voice, "_load_hf_api", lambda: True)
    monkeypatch.setattr(voice, "_transcribe_hf", lambda _path: "schedule a meeting")

    result = voice.transcribe_audio("dummy.webm")

    assert result["success"] is True
    assert result["text"] == "schedule a meeting"
    assert result["source"] == "hf_api"


def test_transcribe_audio_reports_unavailable_when_all_layers_fail(monkeypatch):
    _reset_stt_globals(monkeypatch)
    monkeypatch.setattr(voice, "_load_local_whisper", lambda: False)
    monkeypatch.setattr(voice, "_load_hf_api", lambda: False)

    result = voice.transcribe_audio("dummy.webm", language="fr")

    assert result["success"] is False
    assert result["text"] == ""
    assert result["language"] == "fr"
    assert result["source"] == "error"
    assert "currently unavailable" in result["error"]


def test_transcribe_audio_rejects_silence(monkeypatch):
    _reset_stt_globals(monkeypatch)
    monkeypatch.setattr(voice, "_load_local_whisper", lambda: True)
    monkeypatch.setattr(voice, "_transcribe_local", lambda _path: ("", 0.95))

    result = voice.transcribe_audio("dummy.wav")

    assert result["success"] is False
    assert result["error"].startswith("No speech detected.")


def test_ffmpeg_executable_uses_bundled_fallback(monkeypatch):
    class DummyImageioFfmpeg:
        @staticmethod
        def get_ffmpeg_exe():
            return "bundled-ffmpeg.exe"

    monkeypatch.setattr(voice.shutil, "which", lambda _name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", DummyImageioFfmpeg)

    assert voice._ffmpeg_executable() == "bundled-ffmpeg.exe"
