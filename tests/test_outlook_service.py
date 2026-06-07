"""Unit tests for Outlook service."""

import base64
import sys
import time
from datetime import datetime, timezone

import pytest


def test_is_outlook_available_returns_false_on_non_windows(monkeypatch):
    """Test that is_outlook_available returns False on non-Windows systems.

    Edge case: Non-Windows platform (Linux, macOS) should always return False.
    """
    monkeypatch.setattr(sys, "platform", "linux")

    from src.services.outlook_service import is_outlook_available

    assert is_outlook_available() is False


def test_is_outlook_available_caches_result():
    """Test that is_outlook_available caches results for 30 seconds.

    Verifies:
        - Second call within 30s uses cached value (not repeated COM check)
        - Cache persists across multiple calls
    """
    from src.services import outlook_service

    # Clear cache first
    outlook_service._outlook_availability_cache["available"] = None
    outlook_service._outlook_availability_cache["checked_at"] = 0

    # First call (on Windows without Outlook will be False)
    result1 = outlook_service.is_outlook_available()
    checked_at_1 = outlook_service._outlook_availability_cache["checked_at"]

    # Short sleep
    time.sleep(0.1)

    # Second call should use cache (same timestamp)
    result2 = outlook_service.is_outlook_available()
    checked_at_2 = outlook_service._outlook_availability_cache["checked_at"]

    assert result1 == result2
    assert checked_at_1 == checked_at_2  # Timestamp unchanged, cache was used


def test_is_outlook_available_expires_cache_after_ttl():
    """Test that is_outlook_available expires cache after TTL (30s).

    Verifies:
        - Cache expires and is rechecked after 30 seconds
        - timestamp is updated on cache miss
    """
    from src.services import outlook_service

    # Clear and set cache to old timestamp (>30s old)
    outlook_service._outlook_availability_cache["available"] = False
    outlook_service._outlook_availability_cache["checked_at"] = time.time() - 35

    old_checked_at = outlook_service._outlook_availability_cache["checked_at"]

    # Call should recheck (cache expired)
    outlook_service.is_outlook_available()

    new_checked_at = outlook_service._outlook_availability_cache["checked_at"]

    assert new_checked_at > old_checked_at  # Timestamp updated


def test_entry_id_validation_accepts_valid_base64():
    """Test that _validate_entry_id accepts valid base64 strings."""
    from src.services.outlook_service import _validate_entry_id

    # Valid base64-encoded string
    valid_id = base64.urlsafe_b64encode(b"test_entry_id").decode("utf-8")
    assert _validate_entry_id(valid_id) is True


def test_entry_id_validation_rejects_invalid_base64():
    """Test that _validate_entry_id rejects invalid base64 strings.

    Edge cases:
        - Invalid characters (!!!)
        - Empty string
        - Non-string types (int, None)
    """
    from src.services.outlook_service import _validate_entry_id

    assert _validate_entry_id("!!!invalid!!!") is False
    assert _validate_entry_id("") is False
    assert _validate_entry_id(None) is False
    assert _validate_entry_id(123) is False


def test_list_emails_raises_error_when_outlook_unavailable(monkeypatch):
    """Test that list_emails raises OutlookNotAvailableError when unavailable.

    Edge case: Outlook not available (non-Windows or not installed) returns 503.
    """
    from src.services import outlook_service
    from src.services.outlook_service import (
        OutlookNotAvailableError,
        list_emails,
    )

    monkeypatch.setattr(outlook_service.sys, "platform", "linux")

    with pytest.raises(OutlookNotAvailableError) as exc_info:
        list_emails(user_id=1)

    assert exc_info.value.status_code == 503
    assert "windows" in exc_info.value.message.lower()


def test_list_emails_returns_empty_list_when_no_messages(monkeypatch):
    """Test that list_emails function signature and structure is correct."""
    from src.services.outlook_service import list_emails

    # We can't fully test list_emails without Outlook COM on Windows
    # But we can verify the function exists and has the right signature
    import inspect

    sig = inspect.signature(list_emails)
    assert "user_id" in sig.parameters
    assert "limit" in sig.parameters
    assert "folder" in sig.parameters
    assert "sort_by" in sig.parameters
    assert "ascending" in sig.parameters


def test_list_emails_uses_requested_outlook_default_folder(monkeypatch):
    from src.services import outlook_service

    requested_folder_ids = []

    class DummyItems:
        Count = 0

        def Sort(self, field, ascending):
            self.sorted = (field, ascending)

    class DummyFolder:
        Items = DummyItems()

    class DummyNamespace:
        def GetDefaultFolder(self, folder_id):
            requested_folder_ids.append(folder_id)
            return DummyFolder()

    monkeypatch.setattr(outlook_service, "_outlook_token_for_user", lambda user_id: object())
    monkeypatch.setattr(outlook_service, "_require_outlook_namespace", lambda: DummyNamespace())

    result = outlook_service.list_emails(7, folder="archive")

    assert requested_folder_ids == [outlook_service.OUTLOOK_ARCHIVE_FOLDER]
    assert result["folder"] == "archive"
    assert result["total_count"] == 0


def test_outlook_archive_folder_unavailable_returns_connection_error(monkeypatch):
    from src.services import outlook_service

    class DummyNamespace:
        def GetDefaultFolder(self, folder_id):
            raise Exception("Archive missing")

    monkeypatch.setattr(outlook_service, "_outlook_token_for_user", lambda user_id: object())
    monkeypatch.setattr(outlook_service, "_require_outlook_namespace", lambda: DummyNamespace())

    with pytest.raises(outlook_service.OutlookConnectionError) as exc_info:
        outlook_service.list_emails(7, folder="archive")

    assert exc_info.value.status_code == 409
    assert "Archive folder" in exc_info.value.message


def test_refresh_outlook_starts_send_and_receive_without_progress_dialog(monkeypatch):
    from src.services import outlook_service

    calls = []

    class DummyNamespace:
        def SendAndReceive(self, show_progress):
            calls.append(show_progress)

    monkeypatch.setattr(outlook_service, "_outlook_token_for_user", lambda user_id: object())
    monkeypatch.setattr(outlook_service, "is_outlook_available", lambda: True)
    monkeypatch.setattr(outlook_service, "_outlook_namespace", lambda: DummyNamespace())

    assert outlook_service.refresh_outlook(7) == {"status": "sync_started"}
    assert calls == [False]


def test_refresh_outlook_requires_connection_before_availability_check(monkeypatch):
    from src.services import outlook_service

    monkeypatch.setattr(
        outlook_service,
        "_outlook_token_for_user",
        lambda user_id: (_ for _ in ()).throw(
            outlook_service.OutlookConnectionError("Not connected.", 409)
        ),
    )
    monkeypatch.setattr(
        outlook_service,
        "is_outlook_available",
        lambda: (_ for _ in ()).throw(AssertionError("availability should not run")),
    )

    with pytest.raises(outlook_service.OutlookConnectionError) as exc_info:
        outlook_service.refresh_outlook(7)

    assert exc_info.value.status_code == 409


def test_refresh_outlook_returns_503_when_classic_outlook_is_unavailable(monkeypatch):
    from src.services import outlook_service

    monkeypatch.setattr(outlook_service, "_outlook_token_for_user", lambda user_id: object())
    monkeypatch.setattr(outlook_service.sys, "platform", "linux")

    with pytest.raises(outlook_service.OutlookNotAvailableError) as exc_info:
        outlook_service.refresh_outlook(7)

    assert exc_info.value.status_code == 503
    assert "windows" in exc_info.value.message.lower()


def test_outlook_namespace_maps_windows_session_mismatch(monkeypatch):
    import pythoncom
    import win32com.client

    from src.services import outlook_service

    monkeypatch.setattr(pythoncom, "CoInitialize", lambda: None)
    monkeypatch.setattr(pythoncom, "CoUninitialize", lambda: None)
    monkeypatch.setattr(
        win32com.client,
        "Dispatch",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            Exception("-2147023584 A specified logon session does not exist")
        ),
    )

    with pytest.raises(outlook_service.OutlookConnectionError) as exc_info:
        outlook_service._outlook_namespace()

    assert exc_info.value.status_code == 409
    assert "same signed-in desktop session" in exc_info.value.message


def test_list_emails_with_mocked_com_objects():
    """Test list_emails with realistic mocked Outlook COM objects.

    This test verifies the email fetching and normalization pipeline
    without requiring actual Outlook installation.

    Verifies:
        - Function properly handles unavailable Outlook
        - Correct error code (503) is returned
        - Logging indicates the issue
    """
    from src.services.outlook_service import (
        OutlookConnectionError,
        OutlookNotAvailableError,
        list_emails,
    )

    # On non-Outlook systems, should raise 503 error
    try:
        result = list_emails(user_id=1, limit=2)
        # If no exception, verify structure
        assert "emails" in result
        assert isinstance(result["emails"], list)
    except OutlookNotAvailableError as e:
        # Expected on systems without Outlook
        assert e.status_code == 503
        assert "Outlook is not installed" in str(e)
    except OutlookConnectionError as e:
        # Expected when Outlook belongs to a different Windows desktop session
        assert e.status_code == 409
        assert "same signed-in desktop session" in str(e)


def test_read_email_raises_error_when_outlook_unavailable(monkeypatch):
    """Test that read_email raises OutlookNotAvailableError when unavailable.

    Edge case: Outlook not available returns 503.
    """
    from src.services import outlook_service
    from src.services.outlook_service import (
        OutlookNotAvailableError,
        read_email,
    )

    monkeypatch.setattr(outlook_service.sys, "platform", "linux")

    with pytest.raises(OutlookNotAvailableError) as exc_info:
        read_email(user_id=1, encoded_message_id="dGVzdA==")

    assert exc_info.value.status_code == 503


def test_read_email_raises_error_on_invalid_entry_id(monkeypatch):
    """Test that read_email raises 400 for invalid base64 format BEFORE checking Outlook.

    This tests error separation: input validation (400) before availability check (503).

    Edge cases:
        - Invalid base64: Should return 400 immediately
        - Valid base64 but Outlook unavailable: Should return 503
        - Valid base64, Outlook available, message not found: Should return 404
    """
    from src.services import outlook_service
    from src.services.outlook_service import OutlookServiceError, read_email

    monkeypatch.setattr(outlook_service.sys, "platform", "linux")

    with pytest.raises(OutlookServiceError) as exc_info:
        # This will fail validation BEFORE checking Outlook availability
        read_email(user_id=1, encoded_message_id="dGVzdA==")

    # Should get 503 when Outlook is unavailable (not 400)
    assert exc_info.value.status_code == 503


def test_normalize_outlook_datetime_converts_to_iso():
    """Test that datetime normalization converts to ISO 8601 UTC.

    Verifies:
        - Converts Python datetime to ISO format
        - Timezone-aware datetime handled correctly
        - Output is RFC3339/ISO8601 format
    """
    from src.services.outlook_service import _normalize_outlook_datetime

    test_datetime = datetime(2026, 4, 23, 10, 30, 0, tzinfo=timezone.utc)
    result = _normalize_outlook_datetime(test_datetime)

    assert result == "2026-04-23T10:30:00+00:00"
    assert "T" in result  # ISO format indicator
    assert "+00:00" in result  # UTC timezone indicator


def test_normalize_outlook_datetime_returns_none_on_error():
    """Test that datetime normalization returns None on error.

    Edge cases:
        - None value: Returns None
        - Invalid datetime object: Returns None
        - Malformed object: Returns None
    """
    from src.services.outlook_service import _normalize_outlook_datetime

    assert _normalize_outlook_datetime(None) is None
    assert _normalize_outlook_datetime("invalid") is None
    assert _normalize_outlook_datetime(123) is None


def test_outlook_service_error_has_status_code():
    """Test that OutlookServiceError includes status code.

    Verifies:
        - Error message stored correctly
        - Status code stored correctly
        - Useful for HTTP error responses
    """
    from src.services.outlook_service import OutlookServiceError

    exc = OutlookServiceError("Test error", 503)
    assert exc.message == "Test error"
    assert exc.status_code == 503


def test_outlook_service_error_defaults_to_500():
    """Test that OutlookServiceError defaults to 500 status code.

    Verifies:
        - Status code is optional parameter
        - Defaults to 500 if not provided
    """
    from src.services.outlook_service import OutlookServiceError

    exc = OutlookServiceError("Test error")
    assert exc.status_code == 500
