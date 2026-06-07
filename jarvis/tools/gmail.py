"""
Gmail tool — read, search, send, reply, summarize.
Requires data/google_credentials.json (see _google_auth.py).
"""

from __future__ import annotations

import base64
import email as email_lib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "gmail",
    "description": (
        "Read, search, send, and reply to emails in Gmail. "
        "Use for: checking inbox, reading emails, sending messages, replying to threads, "
        "searching for emails, marking as read. "
        "Actions: list_inbox, read_email, search, send, reply, mark_read, get_unread_count."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_inbox", "read_email", "search", "send", "reply", "mark_read", "get_unread_count"],
                "description": "Action to perform.",
            },
            "query": {
                "type": "string",
                "description": "Gmail search query (for search) or inbox filter (e.g. 'is:unread', 'from:boss@company.com').",
            },
            "email_id": {"type": "string", "description": "Email message ID for read/reply/mark_read."},
            "to": {"type": "string", "description": "Recipient email address for send."},
            "subject": {"type": "string", "description": "Email subject for send."},
            "body": {"type": "string", "description": "Email body text for send or reply."},
            "max_results": {"type": "integer", "description": "Max emails to return (default 5)."},
        },
        "required": ["action"],
    },
}


def _get_service():
    from jarvis.tools._google_auth import get_service
    return get_service("gmail", "v1")


def _decode_body(payload) -> str:
    """Recursively extract plain text from email payload."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace") if data else ""
    if payload.get("mimeType", "").startswith("multipart"):
        for part in payload.get("parts", []):
            text = _decode_body(part)
            if text:
                return text
    return ""


def _header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _format_message(msg: dict, full: bool = False) -> str:
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])
    subject = _header(headers, "subject") or "(no subject)"
    sender = _header(headers, "from")
    date = _header(headers, "date")
    snippet = msg.get("snippet", "")

    if not full:
        return f"ID: {msg['id']}\nFrom: {sender}\nSubject: {subject}\nDate: {date}\nPreview: {snippet}\n"

    body = _decode_body(payload)
    body_preview = body[:1500] + ("…" if len(body) > 1500 else "")
    return f"ID: {msg['id']}\nFrom: {sender}\nSubject: {subject}\nDate: {date}\n\n{body_preview}"


def execute(
    action: str,
    query: str = "",
    email_id: str = "",
    to: str = "",
    subject: str = "",
    body: str = "",
    max_results: int = 5,
) -> str:
    try:
        service = _get_service()
        user = "me"

        if action == "get_unread_count":
            result = service.users().labels().get(userId=user, id="INBOX").execute()
            unread = result.get("messagesUnread", 0)
            total = result.get("messagesTotal", 0)
            return f"Inbox: {unread} unread of {total} total messages."

        if action == "list_inbox":
            q = query or "in:inbox"
            results = service.users().messages().list(
                userId=user, q=q, maxResults=max_results
            ).execute()
            messages = results.get("messages", [])
            if not messages:
                return "No messages found."
            lines = []
            for m in messages:
                msg = service.users().messages().get(userId=user, id=m["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]).execute()
                lines.append(_format_message(msg))
            return "\n".join(lines)

        if action == "search":
            if not query:
                return "Error: query required for search."
            results = service.users().messages().list(
                userId=user, q=query, maxResults=max_results
            ).execute()
            messages = results.get("messages", [])
            if not messages:
                return f"No emails found matching: {query}"
            lines = []
            for m in messages:
                msg = service.users().messages().get(userId=user, id=m["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]).execute()
                lines.append(_format_message(msg))
            return "\n".join(lines)

        if action == "read_email":
            if not email_id:
                return "Error: email_id required."
            msg = service.users().messages().get(userId=user, id=email_id, format="full").execute()
            return _format_message(msg, full=True)

        if action == "mark_read":
            if not email_id:
                return "Error: email_id required."
            service.users().messages().modify(
                userId=user, id=email_id,
                body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return f"Email {email_id} marked as read."

        if action == "send":
            if not to or not body:
                return "Error: 'to' and 'body' are required for send."
            msg = MIMEText(body)
            msg["to"] = to
            msg["subject"] = subject or "(no subject)"
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service.users().messages().send(userId=user, body={"raw": raw}).execute()
            return f"Email sent to {to}."

        if action == "reply":
            if not email_id or not body:
                return "Error: email_id and body required for reply."
            original = service.users().messages().get(userId=user, id=email_id, format="metadata",
                metadataHeaders=["From", "Subject", "Message-ID", "To"]).execute()
            headers = original.get("payload", {}).get("headers", [])
            orig_from = _header(headers, "from")
            orig_subject = _header(headers, "subject")
            orig_msg_id = _header(headers, "message-id")
            thread_id = original.get("threadId", "")

            reply = MIMEText(body)
            reply["to"] = orig_from
            reply["subject"] = f"Re: {orig_subject}" if not orig_subject.startswith("Re:") else orig_subject
            if orig_msg_id:
                reply["In-Reply-To"] = orig_msg_id
                reply["References"] = orig_msg_id

            raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
            service.users().messages().send(
                userId=user,
                body={"raw": raw, "threadId": thread_id}
            ).execute()
            return f"Reply sent to {orig_from}."

        return f"Unknown action: {action}"

    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        log.error(f"gmail failed: {e}")
        return f"Gmail error: {e}"
