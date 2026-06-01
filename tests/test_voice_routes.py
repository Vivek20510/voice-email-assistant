from io import BytesIO

from src.services.tts import SynthesizedAudio


def test_voice_route_returns_transcript(client, monkeypatch):
    monkeypatch.setattr(
        "src.web.voice_routes.transcribe_audio",
        lambda _path: {
            "success": True,
            "text": "show unread emails",
            "source": "local",
        },
    )

    response = client.post(
        "/api/voice/transcribe",
        data={"audio": (BytesIO(b"audio bytes"), "recording.webm")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.json == {
        "success": True,
        "transcript": "show unread emails",
        "source": "local",
    }


def test_voice_route_returns_503_when_stt_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(
        "src.web.voice_routes.transcribe_audio",
        lambda _path: {
            "success": False,
            "error": "Speech recognition is currently unavailable. Please type your query.",
        },
    )

    response = client.post(
        "/api/voice/transcribe",
        data={"audio": (BytesIO(b"audio bytes"), "recording.webm")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 503


def test_voice_route_returns_422_for_silence(client, monkeypatch):
    monkeypatch.setattr(
        "src.web.voice_routes.transcribe_audio",
        lambda _path: {
            "success": False,
            "error": "No speech detected. Please speak clearly and try again.",
        },
    )

    response = client.post(
        "/api/voice/transcribe",
        data={"audio": (BytesIO(b"audio bytes"), "recording.webm")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 422


def test_tts_route_returns_audio_bytes(client, monkeypatch):
    monkeypatch.setattr(
        "src.web.voice_routes.synthesize_speech",
        lambda text, language: SynthesizedAudio(
            audio=b"RIFF....WAVE",
            content_type="audio/wav",
            source="local",
            model_id="facebook/mms-tts-eng",
            language=language,
        ),
    )

    response = client.post(
        "/api/voice/tts",
        json={"text": "Read this summary.", "language": "English", "translate": False},
    )

    assert response.status_code == 200
    assert response.data == b"RIFF....WAVE"
    assert response.content_type == "audio/wav"
    assert response.headers["X-TTS-Source"] == "local"


def test_tts_route_translates_original_body_before_synthesis(client, monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "src.web.voice_routes.translate_text",
        lambda text, language: f"translated:{language}:{text}",
    )

    def fake_synthesize(text, language):
        captured.update({"text": text, "language": language})
        return SynthesizedAudio(b"fLaC", "audio/flac", "hf_api", "model", language)

    monkeypatch.setattr("src.web.voice_routes.synthesize_speech", fake_synthesize)

    response = client.post(
        "/api/voice/tts",
        json={"text": "Original body", "language": "Hindi", "translate": True},
    )

    assert response.status_code == 200
    assert captured == {"text": "translated:Hindi:Original body", "language": "Hindi"}


def test_tts_route_validates_payload_and_rejects_unsupported_language(client):
    assert client.post("/api/voice/tts", data="bad").status_code == 400
    assert client.post("/api/voice/tts", json={"text": "", "language": "English"}).status_code == 400

    response = client.post(
        "/api/voice/tts",
        json={"text": "你好", "language": "Chinese"},
    )

    assert response.status_code == 400
    assert "not yet supported" in response.json["error"]


def test_tts_route_rejects_oversized_text(client, monkeypatch):
    monkeypatch.setattr("src.web.voice_routes.MAX_TTS_TEXT_CHARS", 4)

    response = client.post(
        "/api/voice/tts",
        json={"text": "12345", "language": "English"},
    )

    assert response.status_code == 400
    assert "max 4 characters" in response.json["error"]


def test_tts_route_honors_ai_data_usage_preference(client, monkeypatch):
    monkeypatch.setattr(
        "src.web.ai_guard.is_ai_data_usage_enabled",
        lambda _user_id: False,
    )

    response = client.post(
        "/api/voice/tts",
        json={"text": "Private email", "language": "English"},
    )

    assert response.status_code == 403
    assert response.json["ai_data_usage_enabled"] is False
