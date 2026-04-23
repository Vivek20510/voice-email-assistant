"""Outlook local email service using Windows COM/MAPI interface."""

import base64
import sys
from datetime import datetime, timezone
from typing import Any


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


def is_outlook_available() -> bool:
    """Check if Microsoft Outlook is installed and available on Windows.

    Returns:
        bool: True if Outlook COM is available, False otherwise.
    """
    if sys.platform != "win32":
        return False

    try:
        import win32com.client

        win32com.client.Dispatch("Outlook.Application")

        return True
    except (ImportError, OSError, Exception):
        # ImportError: win32com not installed
        # OSError/Exception: COM initialization failed or Outlook not installed
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
        OutlookNotAvailableError: If Outlook is not installed
    """
    if not is_outlook_available():
        raise OutlookNotAvailableError("Outlook is not installed on this system.", 503)

    try:
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

        # Limit results
        limit = max(1, min(int(limit), 100))

        messages = []
        for idx, item in enumerate(items):
            if idx >= limit:
                break

            try:
                message = _normalize_outlook_message(item)
                messages.append(message)
            except Exception:
                # Skip messages that fail to normalize
                continue

        # Return empty list if no messages
        return {
            "emails": messages,
            "messages": messages,
            "next_page_token": None,
        }

    except Exception as exc:
        raise OutlookNotAvailableError(
            "Failed to access Outlook inbox: " + str(exc), 503
        ) from exc


def read_email(user_id: int, encoded_message_id: str) -> dict:
    """Read a single email from Outlook by EntryID.

    Args:
        user_id: User ID (unused for local Outlook, kept for API consistency)
        encoded_message_id: Base64-encoded Outlook EntryID

    Returns:
        dict: Message details matching Gmail API shape

    Raises:
        OutlookNotAvailableError: If Outlook is not installed
        OutlookServiceError: If message not found or decoding fails
    """
    if not is_outlook_available():
        raise OutlookNotAvailableError("Outlook is not installed on this system.", 503)

    # Decode EntryID from base64
    try:
        entry_id = _decode_entry_id(encoded_message_id)
    except Exception as exc:
        raise OutlookServiceError("Invalid message ID format.", 400) from exc

    try:
        import win32com.client

        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")

        # Get the message by EntryID
        message_item = namespace.GetItemFromID(entry_id)

        if not message_item:
            raise OutlookServiceError("Message not found.", 404)

        return _normalize_outlook_message(message_item)

    except OutlookServiceError:
        raise
    except Exception as exc:
        raise OutlookNotAvailableError(
            "Failed to read message from Outlook: " + str(exc), 503
        ) from exc


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
