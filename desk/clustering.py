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


def cluster_new_items(new_items: list[dict], recent_window_items: list[dict], on_progress=None) -> dict[str, list[int]]:
    clusters: dict[str, list[int]] = {}
    candidates = list({item['id']: item for item in recent_window_items + new_items}.values())
    words = {item['id']: _normalize_title(item.get('title', '')) for item in candidates}
    event_dates = {}
    published_dates = {}
    word_index = {}
    for candidate in candidates:
        for word in words[candidate['id']]:
            word_index.setdefault(word, set()).add(candidate['id'])
    positions = {item['id']: index for index, item in enumerate(candidates)}
    by_id = {item['id']: item for item in candidates}

    def same_window(a, b):
        for row in (a, b):
            item_id = row['id']
            if item_id not in event_dates:
                event_dates[item_id] = _extract_event_date(row)
                published_dates[item_id] = _published_datetime(row)
        event_a, event_b = event_dates[a['id']], event_dates[b['id']]
        if event_a and event_b:
            return event_a.date() == event_b.date()
        pub_a, pub_b = published_dates[a['id']], published_dates[b['id']]
        return not (pub_a and pub_b) or abs((pub_a - pub_b).total_seconds()) <= 48 * 3600
    assigned: dict[int, str] = {}

    for index, item in enumerate(new_items):
        if on_progress and index % 50 == 0:
            on_progress()
        best_match_key = None
        best_match_id = None
        best_score = 0.0

        shared_ids = set()
        for word in words[item['id']]:
            shared_ids.update(word_index[word])
        for other_id in sorted(shared_ids, key=positions.get):
            other = by_id[other_id]
            if other.get("id") == item.get("id"):
                continue
            left, right = words[item['id']], words[other_id]
            score = len(left & right) / len(left | right) if left or right else 0.0
            if score < 0.45 or not same_window(item, other):
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
