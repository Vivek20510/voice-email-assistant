from io import BytesIO


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
