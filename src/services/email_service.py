import base64

import os

from datetime import datetime, timezone

from email.message import EmailMessage

from email.utils import parseaddr, parsedate_to_datetime


import requests


from src.db import db

from src.models import UserToken

from src.services.auth import GOOGLE_TOKEN_URL, compute_expiry

GMAIL_API_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"


class EmailServiceError(Exception):
    """Base error for Gmail-backed email operations."""

    def __init__(self, message: str, status_code: int = 500):

        super().__init__(message)

        self.message = message

        self.status_code = status_code


class GmailConnectionError(EmailServiceError):
    """Raised when the current user has no valid Gmail connection."""


class GmailAPIError(EmailServiceError):
    """Raised when Gmail returns an unexpected API failure."""


GMAIL_FOLDER_LABELS = {
    "inbox": ["INBOX"],
    "draft": ["DRAFT"],
    "sent": ["SENT"],
    "trash": ["TRASH"],
}

GMAIL_ARCHIVE_QUERY = "-in:inbox -in:sent -in:drafts -in:trash -in:spam"


def list_emails(
    user_id: int,
    limit: int = 10,
    page_token: str | None = None,
    label_ids=None,
    folder: str = "inbox",
) -> dict:
    """List Gmail messages for a connected user."""

    user_token = _gmail_token_for_user(user_id)

    params = {"maxResults": max(1, min(int(limit), 50))}

    if page_token:

        params["pageToken"] = page_token

    folder = _normalize_folder(folder)

    if label_ids:

        params["labelIds"] = label_ids

    elif folder in GMAIL_FOLDER_LABELS:

        params["labelIds"] = GMAIL_FOLDER_LABELS[folder]

    elif folder == "archive":

        params["q"] = GMAIL_ARCHIVE_QUERY

    payload = _gmail_request(user_token, "GET", "/messages", params=params)

    messages = payload.get("messages", [])

    normalized_messages = []

    for item in messages:

        detail = _gmail_request(user_token, "GET", f"/messages/{item['id']}")

        normalized_messages.append(_list_shape(_normalize_message(detail)))

    return {
        "emails": normalized_messages,
        "messages": normalized_messages,
        "next_page_token": payload.get("nextPageToken"),
        "total_count": payload.get("resultSizeEstimate", len(normalized_messages)),
        "unread_count": sum(1 for message in normalized_messages if message.get("unread")),
        "folder": folder,
        "channel": "gmail",
    }


def read_email(user_id: int, gmail_id: str) -> dict:
    """Read a single Gmail message."""

    user_token = _gmail_token_for_user(user_id)

    payload = _gmail_request(user_token, "GET", f"/messages/{gmail_id}")

    return _normalize_message(payload)


def send_email(user_id: int, to: str, subject: str, body: str) -> dict:
    """Send an email through the user's connected Gmail account."""

    user_token = _gmail_token_for_user(user_id)

    account_email = user_token.account_email or "me"

    message = EmailMessage()

    message["To"] = to

    message["From"] = account_email

    if subject:

        message["Subject"] = subject

    message.set_content(body)

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    payload = _gmail_request(
        user_token,
        "POST",
        "/messages/send",
        json={"raw": encoded_message},
    )

    return {
        "status": "sent",
        "id": payload.get("id"),
        "thread_id": payload.get("threadId"),
    }


def refresh_gmail_token(user_token: UserToken) -> UserToken:
    """Refresh an expired Gmail access token in-place."""

    if not user_token.refresh_token:

        raise GmailConnectionError(
            "Gmail access has expired. Please reconnect Gmail.", 409
        )

    client_id = os.getenv("GOOGLE_CLIENT_ID")

    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:

        raise GmailAPIError("Missing Google OAuth client configuration.", 500)

    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": user_token.refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=15,
    )

    try:

        response.raise_for_status()

    except requests.HTTPError as exc:

        raise GmailConnectionError(
            "Unable to refresh Gmail access. Please reconnect Gmail.", 409
        ) from exc

    token_data = response.json()

    access_token = token_data.get("access_token")

    if not access_token:

        raise GmailConnectionError(
            "Unable to refresh Gmail access. Please reconnect Gmail.", 409
        )

    user_token.access_token = access_token

    new_refresh_token = token_data.get("refresh_token")

    if new_refresh_token:

        user_token.refresh_token = new_refresh_token

    user_token.expires_at = compute_expiry(token_data.get("expires_in"))

    db.session.commit()

    return user_token


def _gmail_token_for_user(user_id: int) -> UserToken:

    user_token = UserToken.query.filter_by(user_id=user_id, service="gmail").first()

    if user_token is None:

        raise GmailConnectionError("Gmail is not connected for this account.", 409)

    return user_token


def _normalize_folder(folder: str | None) -> str:

    value = (folder or "inbox").strip().lower()

    aliases = {
        "sb-inbox": "inbox",
        "sb-draft": "draft",
        "drafts": "draft",
        "sb-sent": "sent",
        "sentmail": "sent",
        "sent-mail": "sent",
        "sb-archive": "archive",
        "archives": "archive",
        "sb-trash": "trash",
        "deleted": "trash",
        "deleteditems": "trash",
        "deleted-items": "trash",
    }

    value = aliases.get(value, value)

    if value not in {"inbox", "draft", "sent", "archive", "trash"}:

        raise EmailServiceError("Unsupported Gmail folder.", 400)

    return value


def _gmail_request(
    user_token: UserToken,
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: dict | None = None,
    retried: bool = False,
):

    _ensure_access_token(user_token)

    response = requests.request(
        method,
        f"{GMAIL_API_BASE_URL}{path}",
        headers={
            "Authorization": f"Bearer {user_token.access_token}",
            "Accept": "application/json",
        },
        params=params,
        json=json,
        timeout=15,
    )

    if response.status_code == 401 and not retried:

        refresh_gmail_token(user_token)

        return _gmail_request(
            user_token,
            method,
            path,
            params=params,
            json=json,
            retried=True,
        )

    try:

        response.raise_for_status()

    except requests.HTTPError as exc:

        raise GmailAPIError(
            _gmail_error_message(response), response.status_code
        ) from exc

    return response.json()


def _ensure_access_token(user_token: UserToken):

    expires_at = user_token.expires_at

    if expires_at is None:

        return

    if expires_at.tzinfo is None:

        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= datetime.now(timezone.utc):

        refresh_gmail_token(user_token)


def _gmail_error_message(response) -> str:

    try:

        payload = response.json()

    except ValueError:

        return "Gmail API request failed."

    error = payload.get("error")

    if isinstance(error, dict):

        return error.get("message") or "Gmail API request failed."

    if isinstance(error, str):

        return error

    return "Gmail API request failed."


def _normalize_message(message: dict) -> dict:

    payload = message.get("payload") or {}

    headers = {
        (header.get("name") or "").lower(): header.get("value") or ""
        for header in payload.get("headers", [])
    }

    sender_name, sender_email = parseaddr(headers.get("from", ""))

    body_parts = _extract_body(payload)

    return {
        "id": message.get("id"),
        "gmail_id": message.get("id"),
        "sender": sender_name or sender_email or headers.get("from", ""),
        "sender_email": sender_email or None,
        "to": headers.get("to"),
        "cc": headers.get("cc"),
        "bcc": headers.get("bcc"),
        "subject": headers.get("subject"),
        "body_text": body_parts["text"],
        "body_html": body_parts["html"],
        "snippet": message.get("snippet"),
        "received_at": _normalize_datetime(headers.get("date")),
        "unread": "UNREAD" in (message.get("labelIds") or []),
        "labels": message.get("labelIds") or [],
        "channel": "gmail",
    }


def _list_shape(message: dict) -> dict:

    return {
        "id": message["id"],
        "gmail_id": message["gmail_id"],
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


def _extract_body(payload: dict) -> dict:

    body_text = _decode_body(payload.get("body", {}).get("data"))

    mime_type = payload.get("mimeType")

    body_html = None

    if mime_type == "text/html":

        body_html = body_text

        body_text = None

    for part in payload.get("parts", []) or []:

        part_body = _extract_body(part)

        if not body_text and part_body["text"]:

            body_text = part_body["text"]

        if not body_html and part_body["html"]:

            body_html = part_body["html"]

    return {"text": body_text, "html": body_html}


def _decode_body(data: str | None) -> str | None:

    if not data:

        return None

    padding = "=" * (-len(data) % 4)

    decoded = base64.urlsafe_b64decode(f"{data}{padding}")

    return decoded.decode("utf-8", errors="replace")


def _normalize_datetime(value: str | None) -> str | None:

    if not value:

        return None

    try:

        parsed = parsedate_to_datetime(value)

    except (TypeError, ValueError, IndexError):

        return value

    if parsed.tzinfo is None:

        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).isoformat()
