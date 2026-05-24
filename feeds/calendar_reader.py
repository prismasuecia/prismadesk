from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests

from desk.models import NewsItem
from feeds.web_reader import HEADERS


AGENDA_ITEM_RE = re.compile(
    r"^\s*(?P<code>\d{4}/\d{2}:[A-Za-zÅÄÖåäö]+[A-Za-zÅÄÖåäö0-9]*)\s+(?P<title>.+?)\s*$"
)


def _unfold_ical(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        else:
            lines.append(raw_line.rstrip("\r"))
    return lines


def _parse_value(line: str) -> tuple[str, str]:
    key, _, value = line.partition(":")
    return key.split(";", 1)[0], value.replace("\\n", "\n").replace("\\,", ",")


def _parse_dt(value: str) -> str | None:
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
        except ValueError:
            continue
    return value or None


def _agenda_items(description: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for line in description.splitlines():
        match = AGENDA_ITEM_RE.match(line.strip())
        if match:
            items.append((match.group("code"), match.group("title").strip()))
    return items


def _riksdagen_document_url(code: str, fallback_url: str) -> str:
    rm, _, bet = code.partition(":")
    if rm != "2025/26" or not bet:
        return fallback_url
    doc_id = f"HD01{bet}".lower()
    return f"https://www.riksdagen.se/sv/dokument-och-lagar/dokument/betankande/_{doc_id}/"


def _event_blocks(text: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for line in _unfold_ical(text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current:
                events.append(current)
            current = None
            continue
        if current is not None and ":" in line:
            key, value = _parse_value(line)
            current[key] = value

    return events


def read_ical_source(source: dict, timeout: int = 15) -> list[NewsItem]:
    response = requests.get(source["url"], headers=HEADERS, timeout=timeout)
    response.raise_for_status()

    now = datetime.now(timezone.utc)
    items: list[NewsItem] = []
    for event in _event_blocks(response.text):
        starts_at = _parse_dt(event.get("DTSTART", ""))
        if starts_at:
            try:
                if datetime.fromisoformat(starts_at) < now:
                    continue
            except ValueError:
                pass

        title = event.get("SUMMARY", "").strip()
        if not title:
            continue

        description = event.get("DESCRIPTION", "").strip()
        categories = event.get("CATEGORIES", "")
        location = event.get("LOCATION", "")
        uid = event.get("UID", "")
        rest_path = event.get("X-RD-REST", "")
        url = urljoin("https://data.riksdagen.se/", rest_path) if rest_path else f"{source['url']}#{uid}"
        summary = "\n".join(
            part
            for part in [
                f"Start: {starts_at}" if starts_at else "",
                f"Plats: {location}" if location else "",
                f"Kategorier: {categories}" if categories else "",
                description,
            ]
            if part
        )

        agenda_items = _agenda_items(description)
        if agenda_items:
            for code, agenda_title in agenda_items[:30]:
                agenda_summary = "\n".join(
                    part
                    for part in [
                        f"Kalenderhändelse: {title}",
                        f"Ärende: {code}",
                        f"Start: {starts_at}" if starts_at else "",
                        f"Plats: {location}" if location else "",
                        f"Kategorier: {categories}" if categories else "",
                    ]
                    if part
                )
                items.append(
                    NewsItem(
                        source_name=source["name"],
                        source_url=source["url"],
                        title=agenda_title,
                        summary=agenda_summary[:1200],
                        content=agenda_summary[:4000],
                        published_at=starts_at,
                        url=_riksdagen_document_url(code, f"{url}#{code}"),
                        category="parliament_reports",
                        raw_json={
                            "source_type": "ical_agenda_item",
                            "uid": uid,
                            "categories": categories,
                            "agenda_code": code,
                            "calendar_title": title,
                        },
                    )
                )
            continue

        items.append(
            NewsItem(
                source_name=source["name"],
                source_url=source["url"],
                title=title,
                summary=summary[:1200],
                content=summary[:4000],
                published_at=starts_at,
                url=url,
                category=source.get("category", ""),
                raw_json={"source_type": "ical", "uid": uid, "categories": categories},
            )
        )

    def sort_key(item: NewsItem) -> tuple[int, str]:
        return (0 if item.published_at else 1, item.published_at or "")

    return sorted(items, key=sort_key)[:120]
