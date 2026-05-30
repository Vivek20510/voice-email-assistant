"""Helpers for persisted user preferences."""

from src.db import db
from src.models import User, UserPreference


AI_DATA_USAGE_DISABLED_MESSAGE = (
    "AI Data Usage is disabled in Privacy & Security settings."
)


def get_user_preference(user_id: int | None, create: bool = True):
    """Return a user's preferences, creating defaults when requested."""

    if not user_id:
        return None

    user = db.session.get(User, user_id)
    if user is None:
        return None

    preference = UserPreference.query.filter_by(user_id=user_id).first()
    if preference is None and create:
        preference = UserPreference(user_id=user_id, ai_data_usage_enabled=True)
        db.session.add(preference)
        db.session.commit()

    return preference


def is_ai_data_usage_enabled(user_id: int | None) -> bool:
    """Anonymous/test calls remain enabled; logged-in users honor preferences."""

    if not user_id:
        return True

    preference = get_user_preference(user_id)
    if preference is None:
        return True

    return bool(preference.ai_data_usage_enabled)


def set_ai_data_usage_enabled(user_id: int, enabled: bool) -> UserPreference:
    """Persist the AI data usage toggle for a logged-in user."""

    preference = get_user_preference(user_id)
    if preference is None:
        preference = UserPreference(user_id=user_id)
        db.session.add(preference)

    preference.ai_data_usage_enabled = bool(enabled)
    db.session.commit()
    return preference
