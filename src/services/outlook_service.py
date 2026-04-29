import base64
from datetime import datetime, timezone

from src.db import db
from src.models import UserToken
from src.services.email_service import EmailServiceError


OUTLOOK_INBOX_FOLDER = 6
OUTLOOK_MAIL_ITEM_CLASS = 43


class OutlookConnectionError(EmailServiceError):
    """Raised when local Outlook is not connected or unavailable."""


class OutlookAPIError(EmailServiceError):
    """Raised when local Outlook automation fails."""


def connect_outlook(user_id: int) -> dict:
    """Verify local Outlook is available and mark it connected for this user."""
    account_email = _get_account_email()
    token = UserToken.query.filter_by(user_id=user_id, service="outlook").first()
    if token is None:
        token = UserToken(user_id=user_id, service="outlook")
        db.session.add(token)

    token.account_email = account_email
    token.access_token = "local-pywin32"
    token.refresh_token = None
    token.expires_at = None
    db.session.commit()
    return {"message": "Outlook connected.", "account_email": account_email}


def list_emails(user_id: int, limit: int = 10) -> dict:
    """List messages from the local Outlook inbox."""
    _outlook_token_for_user(user_id)
    outlook = _outlook_namespace()
    inbox = outlook.GetDefaultFolder(OUTLOOK_INBOX_FOLDER)
    items = inbox.Items
    items.Sort("[ReceivedTime]", True)

    messages = []
    max_results = max(1, min(int(limit), 50))
    index = 1
    while len(messages) < max_results and index <= items.Count:
        item = items.Item(index)
        index += 1
        if getattr(item, "Class", None) != OUTLOOK_MAIL_ITEM_CLASS:
            continue
        messages.append(_list_shape(_normalize_message(item)))

    return {"emails": messages, "messages": messages, "next_page_token": None}


def read_email(user_id: int, message_id: str) -> dict:
    """Read a single local Outlook message."""
    _outlook_token_for_user(user_id)
    entry_id = _decode_message_id(message_id)
    try:
        item = _outlook_namespace().GetItemFromID(entry_id)
    except Exception as exc:
        raise OutlookAPIError("Unable to load this Outlook message.", 404) from exc
    return _normalize_message(item)


def _outlook_token_for_user(user_id: int) -> UserToken:
    token = UserToken.query.filter_by(user_id=user_id, service="outlook").first()
    if token is None:
        raise OutlookConnectionError("Outlook is not connected for this account.", 409)
    return token


def _outlook_namespace():
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise OutlookConnectionError(
            "pywin32 is not installed. Install pywin32 to connect local Outlook.",
            409,
        ) from exc

    pythoncom.CoInitialize()
    try:
        app = win32com.client.Dispatch("Outlook.Application")
        namespace = app.GetNamespace("MAPI")
        namespace.Logon("", "", False, False)
        return namespace
    except Exception as exc:
        detail = str(exc)
        if "Invalid class string" in detail or "-2147221005" in detail:
            raise OutlookConnectionError(
                "Classic desktop Outlook is not registered for pywin32. "
                "Open or install classic Outlook, not the new Outlook app, then try again.",
                409,
            ) from exc
        raise OutlookConnectionError(
            "Unable to access local Outlook. Open classic Outlook and make sure a profile is configured.",
            409,
        ) from exc


def _get_account_email() -> str | None:
    namespace = _outlook_namespace()
    try:
        address = getattr(namespace.CurrentUser, "Address", None)
        name = getattr(namespace.CurrentUser, "Name", None)
        return address or name
    except Exception:
        return None


def _normalize_message(item) -> dict:
    sender_email = getattr(item, "SenderEmailAddress", None)
    sender_name = getattr(item, "SenderName", None)
    received_at = _normalize_datetime(getattr(item, "ReceivedTime", None))
    categories = getattr(item, "Categories", None)
    labels = [part.strip() for part in str(categories or "").split(",") if part.strip()]
    body_text = getattr(item, "Body", None)
    body_html = getattr(item, "HTMLBody", None)
    subject = getattr(item, "Subject", None)

    return {
        "id": _encode_message_id(getattr(item, "EntryID", "")),
        "gmail_id": None,
        "outlook_id": getattr(item, "EntryID", None),
        "sender": sender_name or sender_email or "Unknown sender",
        "sender_email": sender_email,
        "to": getattr(item, "To", None),
        "cc": getattr(item, "CC", None),
        "bcc": getattr(item, "BCC", None),
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "snippet": _snippet(body_text, body_html),
        "received_at": received_at,
        "unread": bool(getattr(item, "UnRead", False)),
        "labels": labels,
        "channel": "outlook",
    }


def _list_shape(message: dict) -> dict:
    return {
        "id": message["id"],
        "gmail_id": None,
        "outlook_id": message["outlook_id"],
        "sender": message["sender"],
        "sender_email": message["sender_email"],
        "to": message["to"],
        "subject": message["subject"],
        "snippet": message["snippet"],
        "received_at": message["received_at"],
        "unread": message["unread"],
        "labels": message["labels"],
        "channel": message["channel"],
    }


def _encode_message_id(entry_id: str) -> str:
    encoded = base64.urlsafe_b64encode(str(entry_id).encode("utf-8")).decode("ascii")
    return f"outlook:{encoded.rstrip('=')}"


def _decode_message_id(message_id: str) -> str:
    raw = str(message_id or "")
    if raw.startswith("outlook:"):
        raw = raw.split(":", 1)[1]
    padding = "=" * (-len(raw) % 4)
    try:
        return base64.urlsafe_b64decode(f"{raw}{padding}").decode("utf-8")
    except Exception as exc:
        raise OutlookAPIError("Invalid Outlook message id.", 400) from exc


def _normalize_datetime(value) -> str | None:
    if not value:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return str(value)

    if parsed.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo or timezone.utc
        parsed = parsed.replace(tzinfo=local_tz)
    return parsed.astimezone(timezone.utc).isoformat()


def _snippet(body_text: str | None, body_html: str | None) -> str:
    text = (body_text or body_html or "").replace("\r", " ").replace("\n", " ")
    return " ".join(text.split())[:220]
