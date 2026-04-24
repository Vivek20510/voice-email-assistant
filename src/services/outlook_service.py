"""Outlook local email service using Windows COM/MAPI interface."""

import base64
import logging
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Error message constants for consistent messaging
ERROR_OUTLOOK_NOT_AVAILABLE = "Outlook is not installed on this system."
ERROR_OUTLOOK_NOT_FOUND = "Message not found in Outlook."
ERROR_INVALID_ID_FORMAT = "Invalid message ID format (not valid base64)."
ERROR_OUTLOOK_INBOX_FAILURE = "Failed to access Outlook inbox."

# Availability cache: {"available": bool | None, "checked_at": float, "ttl": int}
_outlook_availability_cache = {"available": None, "checked_at": 0, "ttl": 30}


class OutlookServiceError(Exception):
    """Base error for Outlook-backed email operations."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class OutlookNotAvailableError(OutlookServiceError):
    """Raised when Outlook is not installed or unavailable."""


class OutlookNotEnabledError(OutlookServiceError):
    """Raised when Outlook is not enabled/connected for the user."""


def _validate_entry_id(encoded_entry_id: str) -> bool:
    """Validate that the encoded EntryID is valid base64 format.

    Args:
        encoded_entry_id: Base64-encoded EntryID string

    Returns:
        bool: True if valid base64 format, False otherwise

    Note:
        This only validates format, not actual Outlook access.
    """
    if not encoded_entry_id or not isinstance(encoded_entry_id, str):
        return False

    # Check for valid base64 characters only (a-z, A-Z, 0-9, -, _, =)
    if not re.match(r"^[A-Za-z0-9_-]*={0,2}$", encoded_entry_id):
        return False

    try:
        padding = "=" * (-len(encoded_entry_id) % 4)
        base64.urlsafe_b64decode(f"{encoded_entry_id}{padding}")
        return True
    except Exception:
        logger.debug(f"Invalid EntryID format: {encoded_entry_id[:20]}...")
        return False


def _call_with_retry(func, max_retries: int = 2, delay: float = 0.5):
    """Execute a function with retry logic for transient errors.

    Args:
        func: Callable to execute
        max_retries: Maximum retry attempts (default 2)
        delay: Delay in seconds between retries (default 0.5)

    Returns:
        Result of func() if successful

    Raises:
        Exception: If all retries fail

    Note:
        Retries on transient errors (Exception), not on permanent failures
        like ImportError or specific COM errors.
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as exc:
            last_exception = exc
            if attempt < max_retries:
                logger.debug(f"Retry {attempt + 1}/{max_retries} after {delay}s: {exc}")
                time.sleep(delay)
            else:
                logger.warning(f"All {max_retries + 1} attempts failed: {exc}")
    raise last_exception


def is_outlook_available() -> bool:
    """Check if Microsoft Outlook is installed and available on Windows.

    Caches result for 30 seconds to reduce repeated COM initialization.

    Returns:
        bool: True if Outlook COM is available, False otherwise.

    Edge cases:
        - Non-Windows platforms: Always returns False
        - Win32com not installed: Returns False
        - Outlook not installed: Returns False
        - COM initialization timeout: Returns False
    """
    # Check cache
    now = time.time()
    cache = _outlook_availability_cache
    if cache["available"] is not None and (now - cache["checked_at"]) < cache["ttl"]:
        logger.debug(f"Using cached Outlook availability: {cache['available']}")
        return cache["available"]

    logger.debug("Checking Outlook availability...")

    if sys.platform != "win32":
        cache["available"] = False
        cache["checked_at"] = now
        logger.debug("Non-Windows platform detected, Outlook unavailable")
        return False

    try:
        import win32com.client

        win32com.client.Dispatch("Outlook.Application")
        cache["available"] = True
        cache["checked_at"] = now
        logger.debug("Outlook available")
        return True
    except ImportError:
        logger.debug("Win32com not installed")
        cache["available"] = False
        cache["checked_at"] = now
        return False
    except Exception as exc:
        logger.debug(f"Outlook COM initialization failed: {exc}")
        cache["available"] = False
        cache["checked_at"] = now
        return False


def list_emails(
    user_id: int,
    limit: int = 10,
    sort_by: str = "received_time",
    ascending: bool = False,
) -> dict:
    """List emails from the user's Outlook inbox.

    Args:
        user_id: User ID (unused for local Outlook, kept for API consistency)
        limit: Maximum number of emails to return (default 10, max 100)
        sort_by: Field to sort by ("received_time" or "subject")
        ascending: If True, sort ascending; if False (default), descending

    Returns:
        dict: {"emails": [...], "messages": [...]} matching Gmail API shape

    Raises:
        OutlookNotAvailableError: If Outlook is not installed or unavailable

    Edge cases:
        - Empty inbox: Returns empty list
        - Invalid sort_by: Uses received_time
        - Outlook not available: Returns 503 with error message
        - COM timeout: Retries twice before failing
    """
    # Check availability (cached)
    if not is_outlook_available():
        logger.warning(
            f"List emails requested but Outlook unavailable for user {user_id}"
        )
        raise OutlookNotAvailableError(ERROR_OUTLOOK_NOT_AVAILABLE, 503)

    # Sanitize parameters
    limit = max(1, min(int(limit), 100))
    if sort_by not in ("received_time", "subject"):
        sort_by = "received_time"
        logger.debug(f"Invalid sort_by '{sort_by}', using 'received_time'")

    logger.debug(
        f"List emails for user {user_id}: limit={limit}, sort_by={sort_by}, ascending={ascending}"
    )

    def _fetch_from_outlook():
        import win32com.client

        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        inbox = namespace.GetDefaultFolder(6)  # 6 = olFolderInbox

        items = inbox.Items

        # Sort items by received time (descending by default)
        if sort_by == "received_time":
            items.Sort("[ReceivedTime]", not ascending)
        elif sort_by == "subject":
            items.Sort("[Subject]", not ascending)

        messages = []
        for idx, item in enumerate(items):
            if idx >= limit:
                break

            try:
                message = _normalize_outlook_message(item)
                messages.append(message)
            except Exception as exc:
                # Skip messages that fail to normalize
                logger.debug(f"Failed to normalize message at index {idx}: {exc}")
                continue

        return messages

    try:
        messages = _call_with_retry(_fetch_from_outlook, max_retries=1)
        logger.debug(f"Successfully fetched {len(messages)} emails from Outlook")

        return {
            "emails": messages,
            "messages": messages,
            "next_page_token": None,
        }
    except Exception as exc:
        logger.error(f"Failed to access Outlook inbox: {exc}", exc_info=True)
        raise OutlookNotAvailableError(ERROR_OUTLOOK_INBOX_FAILURE, 503) from exc


def read_email(user_id: int, encoded_message_id: str) -> dict:
    """Read a single email from Outlook by EntryID.

    Args:
        user_id: User ID (unused for local Outlook, kept for API consistency)
        encoded_message_id: Base64-encoded Outlook EntryID

    Returns:
        dict: Message details matching Gmail API shape

    Raises:
        OutlookServiceError (400): If message ID format is invalid
        OutlookNotAvailableError (503): If Outlook is not installed
        OutlookServiceError (404): If message not found

    Edge cases:
        - Invalid base64 format: Returns 400 immediately
        - Outlook not available: Returns 503 (checked after format validation)
        - Message not found: Returns 404
        - COM timeout: Retries once before failing with 503
    """
    # VALIDATION STEP: Check format before availability check (returns 400, not 503)
    if not _validate_entry_id(encoded_message_id):
        logger.debug(f"Invalid EntryID format received: {encoded_message_id[:20]}...")
        raise OutlookServiceError(ERROR_INVALID_ID_FORMAT, 400)

    # AVAILABILITY STEP: Check if Outlook is available (returns 503)
    if not is_outlook_available():
        logger.warning(
            f"Read email requested but Outlook unavailable for user {user_id}"
        )
        raise OutlookNotAvailableError(ERROR_OUTLOOK_NOT_AVAILABLE, 503)

    # DECODING STEP: Decode EntryID from base64
    try:
        entry_id = _decode_entry_id(encoded_message_id)
    except Exception as exc:
        logger.debug(f"Failed to decode EntryID: {exc}")
        raise OutlookServiceError(ERROR_INVALID_ID_FORMAT, 400) from exc

    logger.debug(f"Read email for user {user_id}: {encoded_message_id[:20]}...")

    def _fetch_message_from_outlook():
        import win32com.client

        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        message_item = namespace.GetItemFromID(entry_id)

        if not message_item:
            logger.warning(f"Message not found for EntryID: {entry_id[:20]}...")
            raise OutlookServiceError(ERROR_OUTLOOK_NOT_FOUND, 404)

        return _normalize_outlook_message(message_item)

    # OUTLOOK CALL STEP: Fetch from Outlook with retry logic
    try:
        message = _call_with_retry(_fetch_message_from_outlook, max_retries=1)
        logger.debug("Successfully read email from Outlook")
        return message
    except OutlookServiceError:
        raise
    except Exception as exc:
        logger.error(f"Failed to read message from Outlook: {exc}", exc_info=True)
        raise OutlookNotAvailableError(ERROR_OUTLOOK_NOT_AVAILABLE, 503) from exc


def _normalize_outlook_message(item: Any) -> dict:
    """Normalize an Outlook COM item to a standard message dict.

    Args:
        item: Outlook.MailItem COM object

    Returns:
        dict: Normalized message with fields matching Gmail API
    """
    try:
        subject = str(item.Subject or "")
    except Exception:
        subject = ""

    try:
        sender_name = str(item.SenderName or "")
    except Exception:
        sender_name = ""

    try:
        sender_email = str(item.SenderEmailAddress or "")
    except Exception:
        sender_email = ""

    try:
        to = str(item.To or "")
    except Exception:
        to = ""

    # Body/HTMLBody fallback: prefer Body, fall back to HTMLBody
    body_text = None
    body_html = None

    try:
        body_text = str(item.Body or "").strip()
        if not body_text:
            body_text = None
    except Exception:
        body_text = None

    if not body_text:
        try:
            body_html = str(item.HTMLBody or "").strip()
            if not body_html:
                body_html = None
        except Exception:
            body_html = None

    # Fallback: if no body, use empty string
    if not body_text and not body_html:
        body_text = ""

    try:
        entry_id = str(item.EntryID or "")
    except Exception:
        entry_id = ""

    try:
        received_time_str = _normalize_outlook_datetime(item.ReceivedTime)
    except Exception:
        received_time_str = None

    # Encode EntryID for URL-safe use
    encoded_entry_id = _encode_entry_id(entry_id)

    return {
        "id": encoded_entry_id,
        "outlook_entry_id": entry_id,
        "sender": sender_name or sender_email or "Unknown",
        "sender_email": sender_email or None,
        "to": to or None,
        "subject": subject or "(No subject)",
        "body_text": body_text,
        "body_html": body_html,
        "snippet": (body_text or body_html or "")[:100],
        "received_at": received_time_str,
        "unread": False,  # Outlook COM doesn't easily expose unread state
        "labels": [],
        "channel": "outlook",
    }


def _encode_entry_id(entry_id: str) -> str:
    """Encode Outlook EntryID to URL-safe base64.

    Args:
        entry_id: Raw Outlook EntryID string

    Returns:
        str: Base64-encoded (URL-safe) EntryID
    """
    try:
        encoded = base64.urlsafe_b64encode(entry_id.encode("utf-8")).decode("utf-8")
        return encoded
    except Exception:
        return ""


def _decode_entry_id(encoded_entry_id: str) -> str:
    """Decode URL-safe base64 back to Outlook EntryID.

    Args:
        encoded_entry_id: Base64-encoded (URL-safe) EntryID

    Returns:
        str: Raw Outlook EntryID

    Raises:
        Exception: If decoding fails
    """
    padding = "=" * (-len(encoded_entry_id) % 4)
    decoded = base64.urlsafe_b64decode(f"{encoded_entry_id}{padding}")
    return decoded.decode("utf-8", errors="replace")


def _normalize_outlook_datetime(datetime_obj: Any) -> str | None:
    """Convert Outlook DateTime to ISO 8601 UTC format.

    Args:
        datetime_obj: Outlook DateTime COM object

    Returns:
        str: ISO 8601 UTC timestamp, or None if conversion fails
    """
    try:
        # Outlook DateTime is typically a Python datetime object when accessed
        if hasattr(datetime_obj, "year"):
            # It's already a Python datetime-like object
            dt = datetime_obj
        else:
            # Try direct conversion
            return None

        if isinstance(dt, datetime):
            # Ensure timezone awareness
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()

        return None
    except Exception:
        return None
