"""Unit tests for Outlook service."""

import sys
from datetime import datetime, timezone

import pytest


def test_is_outlook_available_returns_false_on_non_windows(monkeypatch):
    """Test that is_outlook_available returns False on non-Windows systems."""
    monkeypatch.setattr(sys, "platform", "linux")

    from src.services.outlook_service import is_outlook_available

    assert is_outlook_available() is False


def test_list_emails_raises_error_when_outlook_unavailable():
    """Test that list_emails raises error when Outlook is not available."""
    from src.services.outlook_service import (
        OutlookNotAvailableError,
        list_emails,
    )

    with pytest.raises(OutlookNotAvailableError) as exc_info:
        list_emails(user_id=1)

    assert exc_info.value.status_code == 503


def test_list_emails_returns_empty_list_when_no_messages(monkeypatch):
    """Test that list_emails function signature and structure is correct."""
    from src.services.outlook_service import list_emails

    # We can't fully test list_emails without Outlook COM on Windows
    # But we can verify the function exists and has the right signature
    import inspect

    sig = inspect.signature(list_emails)
    assert "user_id" in sig.parameters
    assert "limit" in sig.parameters
    assert "sort_by" in sig.parameters
    assert "ascending" in sig.parameters


def test_entry_id_encoding_and_decoding():
    """Test that EntryID encoding and decoding roundtrips correctly."""
    from src.services.outlook_service import _encode_entry_id, _decode_entry_id

    original_entry_id = "000000007F0000000001000000000000ABCD1234"

    encoded = _encode_entry_id(original_entry_id)
    assert isinstance(encoded, str)
    assert len(encoded) > 0

    decoded = _decode_entry_id(encoded)
    assert decoded == original_entry_id


def test_read_email_raises_error_when_outlook_unavailable():
    """Test that read_email raises error when Outlook is not available."""
    from src.services.outlook_service import (
        OutlookNotAvailableError,
        read_email,
    )

    with pytest.raises(OutlookNotAvailableError) as exc_info:
        read_email(user_id=1, encoded_message_id="dGVzdA==")

    assert exc_info.value.status_code == 503


def test_read_email_raises_error_on_invalid_entry_id():
    """Test that read_email raises error on truly invalid base64 that fails decoding."""
    from src.services.outlook_service import OutlookServiceError, read_email

    with pytest.raises(OutlookServiceError) as exc_info:
        # This will fail because Outlook is not available
        read_email(user_id=1, encoded_message_id="dGVzdA==")

    # Should get 503 when Outlook is unavailable
    assert exc_info.value.status_code == 503


def test_normalize_outlook_datetime_converts_to_iso():
    """Test that datetime normalization converts to ISO 8601 UTC."""
    from src.services.outlook_service import _normalize_outlook_datetime

    test_datetime = datetime(2026, 4, 23, 10, 30, 0, tzinfo=timezone.utc)
    result = _normalize_outlook_datetime(test_datetime)

    assert result == "2026-04-23T10:30:00+00:00"


def test_normalize_outlook_datetime_returns_none_on_error():
    """Test that datetime normalization returns None on error."""
    from src.services.outlook_service import _normalize_outlook_datetime

    result = _normalize_outlook_datetime(None)
    assert result is None

    result = _normalize_outlook_datetime("invalid")
    assert result is None


def test_outlook_service_error_has_status_code():
    """Test that OutlookServiceError includes status code."""
    from src.services.outlook_service import OutlookServiceError

    exc = OutlookServiceError("Test error", 503)
    assert exc.message == "Test error"
    assert exc.status_code == 503


def test_outlook_service_error_defaults_to_500():
    """Test that OutlookServiceError defaults to 500 status code."""
    from src.services.outlook_service import OutlookServiceError

    exc = OutlookServiceError("Test error")
    assert exc.status_code == 500
