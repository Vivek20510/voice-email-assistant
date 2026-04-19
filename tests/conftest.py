import pytest
from src.app import create_app
from src.db import db


@pytest.fixture
def app():
    test_config = {
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    }
    app = create_app(test_config=test_config)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        try:
            db.engine.dispose()
        except Exception:
            pass


@pytest.fixture
def client(app):
    return app.test_client()
