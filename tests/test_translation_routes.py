from src.db import db
from src.models import User
from src.services.auth import hash_password


def _log_in(client, app):
    with app.app_context():
        user = User(email="translate@example.com", password_hash=hash_password("Pass123!"))
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    with client.session_transaction() as session:
        session["user_id"] = user_id

    return user_id


def test_language_preference_survives_session_refresh(client, app):
    _log_in(client, app)

    saved = client.post("/api/set-language", json={"language": "Hindi"})
    fetched = client.get("/api/language-preference")

    assert saved.status_code == 200
    assert fetched.status_code == 200
    assert fetched.json == {"success": True, "language": "Hindi"}


def test_translate_uses_persisted_language_when_request_omits_it(
    client,
    app,
    monkeypatch,
):
    _log_in(client, app)
    client.post("/api/set-language", json={"language": "Hindi"})
    captured = {}

    def fake_translate(text, language):
        captured.update({"text": text, "language": language})
        return "अनुवाद"

    monkeypatch.setattr("src.web.translation_routes.translate_text", fake_translate)

    response = client.post("/api/translate", json={"text": "Translation"})

    assert response.status_code == 200
    assert response.json["translated_text"] == "अनुवाद"
    assert captured == {"text": "Translation", "language": "Hindi"}


def test_language_preference_rejects_unsupported_language(client):
    response = client.post("/api/set-language", json={"language": "Klingon"})

    assert response.status_code == 400
    assert response.json == {"success": False, "error": "Unsupported language."}


def test_language_preference_accepts_visible_bengali_option(client):
    response = client.post("/api/set-language", json={"language": "Bengali"})

    assert response.status_code == 200
    assert response.json["language"] == "Bengali"
