from datetime import datetime, timezone
import re

from flask import Blueprint, jsonify, request, session

from src.services.ai_service import MODEL_MODE, generate_response
from src.services.email_service import list_emails as list_gmail_emails
from src.services.outlook_service import list_emails as list_outlook_emails

ai_panel_bp = Blueprint("ai_panel", __name__, url_prefix="/api/ai-panel")

MAX_AI_EMAIL_CONTEXT = 25
MAX_AI_EMAIL_FIELD_CHARS = 500

APP_CAPABILITIES = {
    "dashboard": (
        "The Dashboard is the main workspace for scanning messages, switching "
        "views, opening message detail, and using the AI panel alongside your inbox."
    ),
    "inbox": (
        "Inbox shows loaded Gmail and Outlook messages together. You can ask me "
        "to filter unread, recent, sender, subject, channel, or attachment matches."
    ),
    "gmail": (
        "Gmail is connected from Settings > Channels. Once connected, Gmail "
        "messages appear in the Dashboard and can be filtered with 'show Gmail'."
    ),
    "outlook": (
        "Outlook is connected from Settings > Channels. Once connected, Outlook "
        "messages appear in the Dashboard and can be filtered with 'show Outlook'."
    ),
    "compose": (
        "Compose lets you write a new email or start from an AI draft. Ask me to "
        "open compose, then fill in the recipient, subject, and message."
    ),
    "settings": (
        "Settings manages your profile and connected channels. Use the Channels "
        "tab to connect or review Gmail and Outlook."
    ),
    "channels": (
        "Channels are the mail providers connected to the app. Open Settings > "
        "Channels to connect Gmail or Outlook."
    ),
    "summaries": (
        "Summaries condense a selected message or loaded inbox context into short "
        "takeaways. Ask for a selected-message summary or a dashboard summary."
    ),
    "suggestions": (
        "Suggestions help turn message content into next steps or reply ideas from "
        "the current inbox context."
    ),
    "attachments": (
        "Attachment filters find loaded messages marked with files or attachment "
        "language. Ask 'show emails with attachments' to filter them."
    ),
    "drafts": (
        "Drafts can be started from Compose or from a selected message with 'draft "
        "reply'. The app pre-fills a reply target when message context exists."
    ),
    "navigation": (
        "You can ask me to open compose, open settings, show Gmail, show Outlook, "
        "show unread, show today, or open the most relevant message."
    ),
}

APP_HELP_TOPICS = {
    "dashboard": ["dashboard", "home", "main screen"],
    "inbox": ["inbox", "email", "emails", "message", "messages"],
    "gmail": ["gmail", "google"],
    "outlook": ["outlook", "microsoft"],
    "compose": ["compose", "new email", "write email", "write an email"],
    "settings": ["settings", "profile"],
    "channels": ["channel", "channels", "connect", "connected", "provider"],
    "summaries": ["summary", "summaries", "summarize", "summarise"],
    "suggestions": ["suggestion", "suggestions", "action item", "action items"],
    "attachments": ["attachment", "attachments", "file", "files", "pdf"],
    "drafts": ["draft", "drafts", "reply"],
    "navigation": ["navigate", "navigation", "go to", "open", "show"],
}

APP_HELP_WORDS = [
    "what can",
    "what do",
    "how do",
    "how can",
    "how to",
    "help",
    "explain",
    "guide",
    "where",
    "connect",
    "use",
]

INBOX_CONTEXT_WORDS = [
    "important",
    "needs action",
    "action items",
    "my inbox",
    "my emails",
    "loaded emails",
    "priority",
    "urgent",
]

GREETING_RESPONSE = (
    "Hi, I am your app assistant. I can help you understand the dashboard, "
    "connect Gmail or Outlook, open Compose or Settings, filter your inbox, "
    "summarize messages, and draft replies."
)


def _json_error(message: str, code: int = 400):
    return jsonify({"success": False, "error": message, "code": code}), code


def _clean_text(value, field_name: str | None = None):
    if value is None:
        return ""
    if not isinstance(value, str):
        if field_name:
            raise ValueError(f"{field_name} must be a string.")
        raise ValueError("All fields must be strings.")
    return value.strip()


def _short_text(value, max_chars: int = MAX_AI_EMAIL_FIELD_CHARS) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _has_attachment(email: dict) -> bool:
    attachments = email.get("attachments")
    if isinstance(attachments, list) and attachments:
        return True
    if isinstance(email.get("has_attachments"), bool):
        return email["has_attachments"]
    if isinstance(email.get("hasAttachments"), bool):
        return email["hasAttachments"]
    return False


def _build_email_context(emails) -> str:
    if emails is None:
        emails = []
    if not isinstance(emails, list):
        raise ValueError("Emails must be a list.")

    context_lines = []
    for index, email in enumerate(emails[:MAX_AI_EMAIL_CONTEXT], start=1):
        if not isinstance(email, dict):
            continue

        sender = _short_text(email.get("sender") or email.get("sender_email"))
        subject = _short_text(email.get("subject") or "(No subject)")
        preview = _short_text(
            email.get("body_text") or email.get("snippet") or email.get("body") or ""
        )
        received_at = _short_text(email.get("received_at") or email.get("date"))
        channel = _short_text(email.get("channel") or "email")
        unread = "unread" if email.get("unread") else "read"
        attachment = "has attachments" if _has_attachment(email) else "no attachments"

        context_lines.append(
            "\n".join(
                [
                    f"{index}. From: {sender or 'Unknown sender'}",
                    f"   Subject: {subject}",
                    f"   Preview: {preview or 'No preview available.'}",
                    f"   Received: {received_at or 'Unknown time'}",
                    f"   Channel: {channel}",
                    f"   Status: {unread}; {attachment}",
                ]
            )
        )

    if not context_lines:
        return "No inbox messages are currently loaded in the dashboard."
    return "\n\n".join(context_lines)


def _app_knowledge_context() -> str:
    return "\n".join(
        f"- {topic.title()}: {description}"
        for topic, description in APP_CAPABILITIES.items()
    )


def _build_ai_query_prompt(query: str, emails, include_app_knowledge: bool = False) -> str:
    email_context = _build_email_context(emails)
    app_context = (
        f"\n\nApp knowledge:\n{_app_knowledge_context()}"
        if include_app_knowledge
        else ""
    )
    return f"""
You are helping inside an email dashboard.

Answer the user's question using the loaded inbox context below.

If the inbox context is insufficient, say what is missing instead of inventing details.

Keep the answer concise and practical.

User question:
{query}

Loaded inbox context:
{email_context}
{app_context}
""".strip()


def _email_identity(email: dict) -> tuple[str, str]:
    channel = str(email.get("channel") or "email").strip().lower()
    message_id = (
        email.get("id")
        or email.get("gmail_id")
        or email.get("outlook_id")
        or email.get("subject")
        or ""
    )
    return channel, str(message_id)


def _dedupe_email_context(*email_groups) -> list[dict]:
    seen = set()
    results = []

    for emails in email_groups:
        if not emails:
            continue
        for email in emails:
            if not isinstance(email, dict):
                continue
            identity = _email_identity(email)
            if identity in seen:
                continue
            seen.add(identity)
            results.append(email)

    return results[:MAX_AI_EMAIL_CONTEXT]


def _payload_emails(payload: dict) -> list:
    emails = payload.get("emails", [])
    if emails is None:
        return []
    if not isinstance(emails, list):
        raise ValueError("Emails must be a list.")
    return emails


def _fetch_connected_mail_context(user_id: int | None) -> list[dict]:
    if not user_id:
        return []

    fetched = []
    try:
        gmail_data = list_gmail_emails(user_id, limit=25)
        fetched.extend(gmail_data.get("emails") or gmail_data.get("messages") or [])
    except Exception as exc:
        print("Gmail fetch error:", str(exc))

    try:
        outlook_data = list_outlook_emails(user_id, limit=25)
        fetched.extend(outlook_data.get("emails") or outlook_data.get("messages") or [])
    except Exception as exc:
        print("Outlook fetch error:", str(exc))

    return fetched


def _validate_history(history) -> list[dict]:
    if history is None:
        return []
    if not isinstance(history, list):
        raise ValueError("History must be a list.")

    clean_history = []
    for item in history[-12:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        clean_history.append({"role": role, "content": _short_text(content, 1000)})
    return clean_history


def _context_summary(emails: list[dict]) -> dict:
    summary = {"total": len(emails), "gmail": 0, "outlook": 0}
    for email in emails:
        channel = str(email.get("channel") or "").lower()
        if channel == "gmail":
            summary["gmail"] += 1
        elif channel == "outlook":
            summary["outlook"] += 1
    return summary


def _email_id(email: dict) -> str:
    return str(
        email.get("id")
        or email.get("message_id")
        or email.get("gmail_id")
        or email.get("outlook_id")
        or ""
    )


def _email_card(email: dict) -> dict:
    body = email.get("snippet") or email.get("body_text") or email.get("body") or ""
    return {
        "id": _email_id(email),
        "channel": str(email.get("channel") or "email").lower(),
        "sender": _short_text(email.get("sender") or email.get("sender_email")),
        "subject": _short_text(email.get("subject") or "(No subject)"),
        "snippet": _short_text(body, 220),
        "received_at": _short_text(email.get("received_at") or email.get("date")),
        "unread": bool(email.get("unread")),
        "has_attachments": _has_attachment(email),
    }


def _cards_for(emails: list[dict], limit: int = 10) -> list[dict]:
    return [_email_card(email) for email in emails[:limit] if isinstance(email, dict)]


def _action(action_type: str, label: str, payload: dict | None = None) -> dict:
    return {"type": action_type, "label": label, "payload": payload or {}}


def _structured_response(
    *,
    intent: str,
    response: str,
    emails: list[dict],
    cards: list[dict] | None = None,
    actions: list[dict] | None = None,
    query: str | None = None,
    ai_mode: str | None = None,
    source: str | None = None,
):
    payload = {
        "success": True,
        "intent": intent,
        "response": response,
        "context_summary": _context_summary(emails),
    }
    if query is not None:
        payload["query"] = query
    if ai_mode:
        payload["ai_mode"] = ai_mode
    if source:
        payload["source"] = source
    if cards is not None:
        payload["cards"] = cards
        payload["emails"] = cards
        payload["count"] = len(cards)
    if actions is not None:
        payload["actions"] = actions
    return jsonify(payload)


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _is_greeting(query: str) -> bool:
    q = re.sub(r"[^\w\s]", "", query.lower()).strip()
    return q in {
        "hello",
        "hello ai",
        "hi",
        "hi ai",
        "hey",
        "hey ai",
        "hey assistant",
        "hello assistant",
    }


def _is_help_query(q: str) -> bool:
    return _contains_any(q, APP_HELP_WORDS) or q.endswith("?")


def _app_help_topics(query: str) -> list[str]:
    q = query.lower()
    topics = []
    for topic, keywords in APP_HELP_TOPICS.items():
        if _contains_any(q, keywords):
            topics.append(topic)
    return topics


def _is_app_help_query(query: str) -> bool:
    q = query.lower()
    if _is_greeting(query):
        return False
    if not _is_help_query(q):
        return False
    return bool(_app_help_topics(query)) or _contains_any(q, ["this app", "the app"])


def _is_inbox_context_query(query: str) -> bool:
    q = query.lower()
    if _is_app_help_query(query):
        return False
    return _contains_any(q, INBOX_CONTEXT_WORDS)


def _app_help_response(query: str) -> tuple[str, list[dict]]:
    topics = _app_help_topics(query)
    if not topics:
        topics = ["dashboard", "navigation"]

    selected = []
    for topic in topics:
        if topic not in selected:
            selected.append(topic)
        if len(selected) == 3:
            break

    lines = [APP_CAPABILITIES[topic] for topic in selected]
    actions = []
    q = query.lower()

    if any(topic in selected for topic in ["gmail", "outlook", "channels"]) or "connect" in q:
        actions.append(
            _action("open_settings", "Open channels", {"tab": "channels"})
        )
    if "compose" in selected:
        actions.append(_action("open_compose", "Open compose"))
    if "settings" in selected and not actions:
        actions.append(_action("open_settings", "Open settings", {"tab": "profile"}))

    return " ".join(lines), actions


def detect_intent(query: str) -> str:
    q = query.lower()

    if _is_greeting(query):
        return "greeting"
    if _is_app_help_query(query):
        if _contains_any(q, ["where", "go to", "open", "navigate"]):
            return "navigation_help"
        if _contains_any(q, ["how do", "how can", "how to"]):
            return "how_to"
        if _contains_any(q, ["feature", "explain", "what can", "what do"]):
            return "feature_help"
        return "app_help"

    if _contains_any(q, ["open settings", "go to settings", "settings"]):
        return "navigate_settings"
    if _contains_any(q, ["compose", "new email", "write an email"]):
        return "navigate_compose"
    if _contains_any(q, ["go to gmail", "show gmail", "gmail only"]):
        return "filter_gmail"
    if _contains_any(q, ["go to outlook", "show outlook", "outlook only"]):
        return "filter_outlook"
    if _contains_any(q, ["open email", "open message", "open most relevant"]):
        return "open_message"
    if _contains_any(q, ["summarize selected", "summarise selected"]):
        return "summarize_message"
    if _contains_any(q, ["draft reply", "reply draft", "write a reply"]):
        return "draft_reply"
    if any(k in q for k in ["summarize", "summarise"]) and any(
        k in q for k in ["today", "recent", "latest"]
    ):
        return "ai"
    if any(k in q for k in ["attachment", "attachments", "files", "pdf"]):
        return "filter_attachments"
    if any(k in q for k in ["unread", "not read"]):
        return "filter_unread"
    if any(k in q for k in ["today", "recent", "latest"]):
        return "filter_recent"
    if re.search(r"\b(from|sender)\s+[\w@.\- ]+", q):
        return "filter_sender"
    if re.search(r"\b(subject|about)\s+[\w@.\- ]+", q):
        return "filter_subject"

    return "ai"


def _extract_after(query: str, prefixes: list[str]) -> str:
    for prefix in prefixes:
        match = re.search(rf"\b{re.escape(prefix)}\s+(.+)$", query, re.IGNORECASE)
        if match:
            value = match.group(1)
            value = re.split(
                r"\b(with attachments|unread|today|gmail only|outlook only)\b",
                value,
                flags=re.IGNORECASE,
            )[0]
            return value.strip(" .?!")
    return ""


def _matches_text(value, needle: str) -> bool:
    return needle.lower() in str(value or "").lower()


def filter_emails_by_channel(emails, channel: str):
    return [
        e
        for e in emails
        if str(e.get("channel") or "").strip().lower() == channel.lower()
    ]


def filter_emails_by_sender(emails, sender: str):
    if not sender:
        return []
    return [
        e
        for e in emails
        if _matches_text(e.get("sender"), sender)
        or _matches_text(e.get("sender_email"), sender)
    ]


def filter_emails_by_subject(emails, keyword: str):
    if not keyword:
        return []
    return [e for e in emails if _matches_text(e.get("subject"), keyword)]


def filter_emails_by_attachment(emails):
    results = []
    for email in emails:
        if email.get("has_attachments"):
            results.append(email)
            continue

        attachments = email.get("attachments")
        if isinstance(attachments, list) and attachments:
            results.append(email)
            continue

        text = (
            (email.get("snippet") or "") + " " + (email.get("body_text") or "")
        ).lower()
        if any(
            keyword in text
            for keyword in ["attach", "attachment", "enclosed", "pdf", "file"]
        ):
            results.append(email)

    return results


def filter_unread_emails(emails):
    return [e for e in emails if e.get("unread")]


def filter_recent_emails(emails):
    today = datetime.now(timezone.utc).date()
    results = []

    for email in emails:
        ts = email.get("received_at")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.date() == today:
            results.append(email)

    return results


def _most_relevant_email(emails: list[dict], query: str, active_message_id: str = ""):
    if active_message_id:
        for email in emails:
            if _email_id(email) == str(active_message_id):
                return email

    sender = _extract_after(query, ["from", "sender"])
    if sender:
        matches = filter_emails_by_sender(emails, sender)
        if matches:
            return matches[0]

    subject = _extract_after(query, ["subject", "about"])
    if subject:
        matches = filter_emails_by_subject(emails, subject)
        if matches:
            return matches[0]

    unread = filter_unread_emails(emails)
    return (unread or emails or [None])[0]


@ai_panel_bp.route("/query", methods=["POST"])
def ai_query():
    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return _json_error("Valid JSON payload required.")

    try:
        query = _clean_text(payload.get("query"))
        user_id = session.get("user_id") or payload.get("user_id")
        active_view = _clean_text(payload.get("active_view"), "active_view")
        active_message_id = _clean_text(
            payload.get("active_message_id"),
            "active_message_id",
        )
        history = _validate_history(payload.get("history"))

        if not query:
            return _json_error("Query is required.")

        request_emails = _payload_emails(payload)
        fetched_emails = _fetch_connected_mail_context(user_id)
        emails = _dedupe_email_context(request_emails, fetched_emails)
        intent = detect_intent(query)

        if intent == "greeting":
            return _structured_response(
                intent=intent,
                response=GREETING_RESPONSE,
                emails=emails,
                actions=[
                    _action("open_compose", "Open compose"),
                    _action("open_settings", "Connect channels", {"tab": "channels"}),
                ],
                source="conversation",
            )

        if intent in {"app_help", "feature_help", "navigation_help", "how_to"}:
            response_text, actions = _app_help_response(query)
            return _structured_response(
                intent=intent,
                response=response_text,
                emails=emails,
                actions=actions,
                source="app_knowledge",
            )

        if intent == "navigate_settings":
            return _structured_response(
                intent=intent,
                response="Opening settings.",
                emails=emails,
                actions=[
                    _action(
                        "open_settings",
                        "Open settings",
                        {
                            "tab": (
                                "channels" if "channel" in query.lower() else "profile"
                            )
                        },
                    )
                ],
                source="navigation",
            )

        if intent == "navigate_compose":
            return _structured_response(
                intent=intent,
                response="Opening compose.",
                emails=emails,
                actions=[_action("open_compose", "Open compose")],
                source="navigation",
            )

        channel_filters = {"filter_gmail": "gmail", "filter_outlook": "outlook"}
        if intent in channel_filters:
            channel = channel_filters[intent]
            results = filter_emails_by_channel(emails, channel)
            cards = _cards_for(results)
            return _structured_response(
                intent=intent,
                response=f"Found {len(results)} {channel.title()} emails.",
                emails=emails,
                cards=cards,
                actions=[
                    _action(
                        "filter_view",
                        f"Show {channel.title()}",
                        {
                            "channel": channel,
                            "message_ids": [card["id"] for card in cards],
                        },
                    )
                ],
                source="inbox_context",
            )

        if intent == "filter_attachments":
            try:
                results = filter_emails_by_attachment(emails)
                cards = _cards_for(results)
                return _structured_response(
                    intent=intent,
                    response=f"Found {len(results)} emails with attachments.",
                    emails=emails,
                    cards=cards,
                    actions=[
                        _action(
                            "filter_view",
                            "Show attachments",
                            {
                                "has_attachments": True,
                                "message_ids": [card["id"] for card in cards],
                            },
                        )
                    ],
                    source="inbox_context",
                )
            except Exception as exc:
                print("Attachment filter error:", str(exc))
                return _json_error("Failed to filter attachments.")

        if intent == "filter_unread":
            results = filter_unread_emails(emails)
            cards = _cards_for(results)
            return _structured_response(
                intent=intent,
                response=f"You have {len(results)} unread emails.",
                emails=emails,
                cards=cards,
                actions=[
                    _action(
                        "filter_view",
                        "Show unread",
                        {"unread": True, "message_ids": [card["id"] for card in cards]},
                    )
                ],
                source="inbox_context",
            )

        if intent == "filter_recent":
            results = filter_recent_emails(emails)
            cards = _cards_for(results)
            return _structured_response(
                intent=intent,
                response=f"Found {len(results)} emails from today.",
                emails=emails,
                cards=cards,
                actions=[
                    _action(
                        "filter_view",
                        "Show today",
                        {"today": True, "message_ids": [card["id"] for card in cards]},
                    )
                ],
                source="inbox_context",
            )

        if intent == "filter_sender":
            sender = _extract_after(query, ["from", "sender"])
            results = filter_emails_by_sender(emails, sender)
            cards = _cards_for(results)
            return _structured_response(
                intent=intent,
                response=(
                    f"Found {len(results)} emails from {sender}."
                    if sender
                    else "Tell me which sender to search for."
                ),
                emails=emails,
                cards=cards,
                actions=(
                    [
                        _action(
                            "filter_view",
                            "Show sender",
                            {
                                "sender": sender,
                                "message_ids": [card["id"] for card in cards],
                            },
                        )
                    ]
                    if sender
                    else []
                ),
                source="inbox_context",
            )

        if intent == "filter_subject":
            keyword = _extract_after(query, ["subject", "about"])
            results = filter_emails_by_subject(emails, keyword)
            cards = _cards_for(results)
            return _structured_response(
                intent=intent,
                response=(
                    f'Found {len(results)} emails matching "{keyword}".'
                    if keyword
                    else "Tell me which subject keyword to search for."
                ),
                emails=emails,
                cards=cards,
                actions=(
                    [
                        _action(
                            "filter_view",
                            "Show subject",
                            {
                                "subject": keyword,
                                "message_ids": [card["id"] for card in cards],
                            },
                        )
                    ]
                    if keyword
                    else []
                ),
                source="inbox_context",
            )

        if intent in {"open_message", "summarize_message", "draft_reply"}:
            message = _most_relevant_email(emails, query, active_message_id)
            if not message:
                return _structured_response(
                    intent=intent,
                    response="I need an email selected or matching results to do that.",
                    emails=emails,
                    cards=[],
                    actions=[],
                    source="inbox_context",
                )

            card = _email_card(message)
            action_type = {
                "open_message": "open_message",
                "summarize_message": "summarize_message",
                "draft_reply": "prefill_compose",
            }[intent]
            action_label = {
                "open_message": "Open message",
                "summarize_message": "Summarize message",
                "draft_reply": "Draft reply",
            }[intent]
            action_payload = {"message_id": card["id"], "channel": card["channel"]}
            if intent == "draft_reply":
                action_payload.update(
                    {
                        "to": card["sender"],
                        "subject": f"Re: {card['subject']}",
                        "body": "",
                    }
                )

            return _structured_response(
                intent=intent,
                response=f"{action_label}: {card['subject']}",
                emails=emails,
                cards=[card],
                actions=[_action(action_type, action_label, action_payload)],
                source="inbox_context",
            )

        if not emails:
            return _structured_response(
                intent="insufficient_context",
                response="I need emails loaded before I can answer from your inbox.",
                emails=emails,
                cards=[],
                actions=[],
                source="inbox_context",
            )

        try:
            prompt = _build_ai_query_prompt(
                query,
                emails,
                include_app_knowledge=not _is_inbox_context_query(query),
            )
            if history:
                turns = "\n".join(
                    f"{turn['role']}: {turn['content']}" for turn in history
                )
                prompt = f"{prompt}\n\nConversation so far:\n{turns}"
            if active_view:
                prompt = f"{prompt}\n\nActive dashboard view: {active_view}"

            ai_response = generate_response(prompt)
            return _structured_response(
                intent=intent,
                ai_mode=MODEL_MODE,
                query=query,
                response=ai_response,
                emails=emails,
                source="inbox_context",
            )
        except ValueError as exc:
            return _json_error(str(exc), 400)
        except Exception as exc:
            print("AI Query Error:", str(exc))
            return _json_error("AI query failed.", 500)

    except ValueError as exc:
        return _json_error(str(exc))
