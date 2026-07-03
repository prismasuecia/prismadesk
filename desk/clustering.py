from __future__ import annotations

import re
from datetime import datetime

from desk.scoring import detect_swedish_event_datetime, parse_item_datetime


STOPWORDS = {"i", "på", "och", "en", "ett", "att", "för", "med", "av", "till", "om", "är"}


def _normalize_title(title: str) -> set[str]:
    words = re.findall(r"[a-zåäöA-ZÅÄÖ0-9]+", title.lower())
    return {word for word in words if word not in STOPWORDS and len(word) > 2}


def _extract_event_date(item: dict) -> datetime | None:
    text = f"{item.get('title', '')} {item.get('summary', '')}"
    return detect_swedish_event_datetime(text)


def _published_datetime(item: dict) -> datetime | None:
    return parse_item_datetime(item.get("published_at") or item.get("fetched_at"))


def _similarity(a: dict, b: dict) -> float:
    title_a = _normalize_title(a.get("title", ""))
    title_b = _normalize_title(b.get("title", ""))
    if not title_a or not title_b:
        return 0.0
    return len(title_a & title_b) / len(title_a | title_b)


def _same_time_window(a: dict, b: dict) -> bool:
    event_a = _extract_event_date(a)
    event_b = _extract_event_date(b)
    if event_a and event_b:
        return event_a.date() == event_b.date()

    published_a = _published_datetime(a)
    published_b = _published_datetime(b)
    if published_a and published_b:
        return abs((published_a - published_b).total_seconds()) <= 48 * 3600
    return True


def cluster_new_items(new_items: list[dict], recent_window_items: list[dict]) -> dict[str, list[int]]:
    clusters: dict[str, list[int]] = {}
    candidates = recent_window_items + new_items
    assigned: dict[int, str] = {}

    for item in new_items:
        best_match_key = None
        best_match_id = None
        best_score = 0.0

        for other in candidates:
            if other.get("id") == item.get("id"):
                continue
            score = _similarity(item, other)
            if score < 0.45 or not _same_time_window(item, other):
                continue
            if score > best_score:
                best_score = score
                best_match_id = other["id"]
                best_match_key = assigned.get(other["id"]) or f"cluster_{other['id']}"

        key = best_match_key or f"cluster_{item['id']}"
        assigned[item["id"]] = key
        clusters.setdefault(key, [])
        if best_match_id and best_match_id not in clusters[key]:
            clusters[key].append(best_match_id)
        if item["id"] not in clusters[key]:
            clusters[key].append(item["id"])

    return clusters
