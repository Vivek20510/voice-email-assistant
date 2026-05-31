"""Helpers for persisted user preferences."""

from src.db import db
from src.models import User, UserPreference


AI_DATA_USAGE_DISABLED_MESSAGE = (
    "AI Data Usage is disabled in Privacy & Security settings."
)
DEFAULT_LANGUAGE = "English"
SUPPORTED_LANGUAGES = (
    "English",
    "Hindi",
    "Telugu",
    "Tamil",
    "Kannada",
    "Bengali",
    "French",
    "Spanish",
    "German",
    "Arabic",
    "Chinese",
    "Japanese",
)


def normalize_language(language: str | None) -> str:
    """Return a supported language name or raise for an invalid preference."""

    if not isinstance(language, str):
        raise ValueError("language must be a string.")

    normalized = language.strip()
    if normalized not in SUPPORTED_LANGUAGES:
        raise ValueError("Unsupported language.")

    return normalized


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


def get_preferred_language(user_id: int | None) -> str:
    """Return a user's stored language, falling back to English."""

    preference = get_user_preference(user_id)
    if preference is None:
        return DEFAULT_LANGUAGE

    return preference.preferred_language or DEFAULT_LANGUAGE


def set_preferred_language(user_id: int, language: str) -> UserPreference:
    """Persist the selected language for a logged-in user."""

    preference = get_user_preference(user_id)
    if preference is None:
        preference = UserPreference(user_id=user_id)
        db.session.add(preference)

    preference.preferred_language = normalize_language(language)
    db.session.commit()
    return preference
