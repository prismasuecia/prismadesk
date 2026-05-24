from __future__ import annotations

import imaplib
import os
import ssl
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from desk.models import NewsItem


def _decode(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _message_text(message) -> str:
    parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
    else:
        payload = message.get_payload(decode=True)
        if payload:
            parts.append(payload.decode(message.get_content_charset() or "utf-8", errors="replace"))
    return "\n".join(parts).strip()


def mail_enabled() -> bool:
    return os.getenv("ENABLE_MAIL", "false").lower() == "true" and bool(
        os.getenv("PRISMA_MAIL_USER") and os.getenv("PRISMA_MAIL_PASSWORD")
    )


def read_recent_mail(limit: int = 50) -> list[NewsItem]:
    if not mail_enabled():
        return []

    host = os.getenv("PRISMA_MAIL_HOST", "imap.one.com")
    port = int(os.getenv("PRISMA_MAIL_PORT", "993"))
    user = os.getenv("PRISMA_MAIL_USER", "")
    password = os.getenv("PRISMA_MAIL_PASSWORD", "")

    context = ssl.create_default_context()
    items: list[NewsItem] = []
    with imaplib.IMAP4_SSL(host, port, ssl_context=context) as client:
        client.login(user, password)
        client.select("INBOX", readonly=True)
        _, data = client.search(None, "UNSEEN")
        ids = data[0].split()[-limit:]

        for message_id in reversed(ids):
            _, msg_data = client.fetch(message_id, "(RFC822)")
            raw = msg_data[0][1]
            message = message_from_bytes(raw)
            subject = _decode(message.get("Subject"))
            sender = _decode(message.get("From"))
            date_header = message.get("Date")
            published_at = parsedate_to_datetime(date_header).isoformat() if date_header else None
            body = _message_text(message)

            items.append(
                NewsItem(
                    source_name=f"Mail: {sender}",
                    source_url="imap://INBOX",
                    title=subject or "(utan ämne)",
                    summary=body[:500],
                    content=body[:4000],
                    published_at=published_at,
                    url="",
                    category="mail",
                    raw_json={"source_type": "imap", "from": sender},
                )
            )

    return items
