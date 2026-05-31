from sqlalchemy import inspect

from src.db import db
from src.models import User, UserPreference
from src.services.auth import hash_password
from src.services.preferences import (
    get_user_preference,
    is_ai_data_usage_enabled,
    set_ai_data_usage_enabled,
    get_preferred_language,
    set_preferred_language,
)


def test_user_preference_defaults_ai_data_usage_enabled(app):
    with app.app_context():
        user = User(email="prefs@example.com", password_hash=hash_password("Pass123!"))
        db.session.add(user)
        db.session.commit()

        preference = get_user_preference(user.id)

        assert preference is not None
        assert preference.ai_data_usage_enabled is True
        assert is_ai_data_usage_enabled(user.id) is True


def test_ai_data_usage_preference_can_be_disabled(app):
    with app.app_context():
        user = User(email="disabled@example.com", password_hash=hash_password("Pass123!"))
        db.session.add(user)
        db.session.commit()

        preference = set_ai_data_usage_enabled(user.id, False)

        assert preference.ai_data_usage_enabled is False
        assert is_ai_data_usage_enabled(user.id) is False


def test_preferred_language_can_be_persisted(app):
    with app.app_context():
        user = User(email="language@example.com", password_hash=hash_password("Pass123!"))
        db.session.add(user)
        db.session.commit()

        assert get_preferred_language(user.id) == "English"

        preference = set_preferred_language(user.id, "Hindi")

        assert preference.preferred_language == "Hindi"
        assert get_preferred_language(user.id) == "Hindi"


def test_schema_compatibility_has_user_preferences_table(app):
    with app.app_context():
        inspector = inspect(db.engine)
        columns = {
            column["name"]
            for column in inspector.get_columns(UserPreference.__tablename__)
        }

        assert UserPreference.__tablename__ in inspector.get_table_names()
        assert "user_id" in columns
        assert "ai_data_usage_enabled" in columns
        assert "preferred_language" in columns
