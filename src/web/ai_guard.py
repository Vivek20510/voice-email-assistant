"""Shared request guard for AI data usage preferences."""

from flask import jsonify, session

from src.services.preferences import (
    AI_DATA_USAGE_DISABLED_MESSAGE,
    is_ai_data_usage_enabled,
)


def require_ai_data_usage_enabled():
    """Return a Flask response tuple when AI usage is disabled."""

    if is_ai_data_usage_enabled(session.get("user_id")):
        return None

    return (
        jsonify(
            {
                "success": False,
                "error": AI_DATA_USAGE_DISABLED_MESSAGE,
                "code": 403,
                "ai_data_usage_enabled": False,
            }
        ),
        403,
    )
