from __future__ import annotations

import yaml
import os
import time
from dotenv import load_dotenv
from pathlib import Path

from ai.classifier import classify_item
from desk import database
from desk.clustering import cluster_new_items
from desk.models import NewsItem
from desk.scoring import stable_item_hash
from feeds.rss_reader import read_rss_source
from feeds.calendar_reader import read_ical_source
from feeds.web_reader import read_web_source
from prisma_site.duplicate_checker import apply_prisma_status, fetch_prisma_articles


BASE_DIR = Path(__file__).resolve().parents[1]
WEB_REQUEST_MAX_SECONDS = 14.0
WEB_REQUEST_MAX_SOURCES = 25
SOURCE_PRIORITY_ORDER = {
    "red": 0,
    "orange": 1,
    "yellow": 2,
    "blue": 3,
    "green": 4,
}
DEFAULT_DESK_MIX_SOURCE_NAMES = [
    "Regeringen pressmeddelanden web",
    "UD avrådan",
    "Via TT",
    "Prisma webbsök UD Latinamerika",
    "Prisma webbsök partiförslag migration integration",
    "Prisma webbsök SD slöjförbud",
    "DN Kalendariet",
    "Visit Stockholm events",
    "Stockholm Pride nyheter",
    "Stockholm Pride pressackreditering",
    "Prisma webbsök migration",
    "Prisma webbsök arbete ekonomi",
    "Prisma webbsök lagar samhälle",
    "Prisma webbsök vardag myndigheter",
    "Prisma webbsök kultur latino Stockholm",
    "Songkick Stockholm alla konserter",
    "Debaser Stockholm kalender",
    "Casa Latina Sverige",
    "Instituto Cervantes Stockholm",
    "Stockholms stad aktuellt",
    "Stockholms stad Via TT",
    "Polisen press Stockholm",
    "Riksdagen kalender kammaren",
    "Riksdagen betänkanden förslag",
    "Riksdagen propositioner",
    "Försvarsmakten Mynewsdesk event",
    "Regeringen pressmeddelanden",
]


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_sources() -> list[dict]:
    sources = load_yaml(BASE_DIR / "config" / "sources.yaml").get("sources", [])
    limit = int(os.getenv("PRISMA_SOURCE_LIMIT", "0") or "0")
    if limit > 0:
        indexed_sources = list(enumerate(sources))
        indexed_sources.sort(
            key=lambda pair: (
                SOURCE_PRIORITY_ORDER.get(str(pair[1].get("priority", "")).lower(), 9),
                pair[0],
            )
        )
        return [source for _, source in indexed_sources[:limit]]
    return sources


def clamp_sources_for_web_request(sources: list[dict]) -> list[dict]:
    if os.getenv("PRISMA_ALLOW_LONG_UPDATE", "false").lower() == "true":
        return sources
    by_name = {source.get("name"): source for source in sources}
    selected: list[dict] = []
    seen: set[str] = set()

    for name in DEFAULT_DESK_MIX_SOURCE_NAMES:
        source = by_name.get(name)
        if source and name not in seen:
            selected.append(source)
            seen.add(name)

    for source in sources:
        name = source.get("name")
        if name in seen:
            continue
        selected.append(source)
        seen.add(name)
        if len(selected) >= WEB_REQUEST_MAX_SOURCES:
            break

    return selected[:WEB_REQUEST_MAX_SOURCES]


def clamp_seconds_for_web_request(max_seconds: float) -> float:
    if os.getenv("PRISMA_ALLOW_LONG_UPDATE", "false").lower() == "true":
        return max_seconds
    if max_seconds <= 0:
        return WEB_REQUEST_MAX_SECONDS
    return min(max_seconds, WEB_REQUEST_MAX_SECONDS)


def count_configured_sources() -> int:
    return len(load_yaml(BASE_DIR / "config" / "sources.yaml").get("sources", []))


def fetch_source(source: dict) -> list[NewsItem]:
    timeout = int(os.getenv("PRISMA_SOURCE_FETCH_TIMEOUT", "3"))
    if source.get("type") == "rss":
        return read_rss_source(source, timeout=timeout)
    if source.get("type") == "ical":
        return read_ical_source(source, timeout=timeout)
    return read_web_source(source, timeout=timeout)


def _maybe_read_mail() -> list[NewsItem]:
    if os.getenv("ENABLE_MAIL", "false").lower() != "true":
        return []
    try:
        from mail.imap_reader import read_recent_mail
    except ModuleNotFoundError:
        return []
    return read_recent_mail()


def run_update() -> dict:
    load_dotenv(BASE_DIR / ".env")
    database.init_db()
    run_id = database.start_run()
    started = time.monotonic()
    max_seconds = clamp_seconds_for_web_request(
        float(os.getenv("PRISMA_UPDATE_MAX_SECONDS", "0") or "0")
    )
    errors: list[str] = []
    all_items: list[NewsItem] = []
    prisma_articles = []
    all_sources = load_yaml(BASE_DIR / "config" / "sources.yaml").get("sources", [])
    configured_sources = len(all_sources)
    configured_selected_sources = load_sources()
    selected_sources = clamp_sources_for_web_request(configured_selected_sources)
    sources_attempted = 0
    sources_failed = 0
    sources_skipped = max(configured_sources - len(selected_sources), 0)
    sources_skipped_names = [
        source.get("name", "Okänd källa")
        for source in all_sources
        if source not in selected_sources
    ]

    try:
        site_url = __import__("os").getenv("PRISMA_SITE_URL", "https://www.prismasuecia.se")
        try:
            prisma_articles = fetch_prisma_articles(site_url)
            database.save_prisma_articles(prisma_articles)
        except Exception as exc:
            errors.append(f"Prisma site: {exc}")

        for source in selected_sources:
            if max_seconds and time.monotonic() - started > max_seconds:
                remaining_sources = selected_sources[sources_attempted:]
                errors.append(
                    f"Tidsbudget nådd efter {int(max_seconds)} sekunder. Kör igen för fler källor."
                )
                sources_skipped += len(remaining_sources)
                sources_skipped_names.extend(
                    source.get("name", "Okänd källa") for source in remaining_sources
                )
                break
            sources_attempted += 1
            try:
                source_items = fetch_source(source)
                database.update_source_health(source.get("name", "Okänd källa"), len(source_items))
                all_items.extend(source_items)
            except Exception as exc:
                sources_failed += 1
                database.update_source_health(source.get("name", "Okänd källa"), 0)
                errors.append(f"{source.get('name', 'Okänd källa')}: {exc}")

        try:
            all_items.extend(_maybe_read_mail())
        except Exception as exc:
            errors.append(f"Mail: {exc}")

        unique_items: dict[str, NewsItem] = {}
        for item in all_items:
            item.hash = stable_item_hash(item)
            unique_items[item.hash] = item

        rules = load_yaml(BASE_DIR / "config" / "rules.yaml")
        classified: list[NewsItem] = []
        for item in unique_items.values():
            classify_item(item, rules)
            apply_prisma_status(item, prisma_articles)
            from desk.scoring import calculate_score

            item.score = calculate_score(item)
            classified.append(item)

        saved_count = database.save_items(classified, run_id=run_id)
        run_items = [dict(row) for row in database.items_for_run(run_id, limit=1000)]
        recent_items = [dict(row) for row in database.items_in_window(hours=72)]
        clusters = cluster_new_items(run_items, recent_items)
        for cluster_key, item_ids in clusters.items():
            if len(item_ids) > 1:
                database.save_cluster(cluster_key, item_ids)
        red_alerts = sum(1 for item in classified if item.priority == "RED")
        source_stats = {
            "configured": configured_sources,
            "selected": len(selected_sources),
            "attempted": sources_attempted,
            "failed": sources_failed,
            "skipped": sources_skipped,
            "skipped_names": sources_skipped_names,
        }
        database.finish_run(
            run_id,
            "OK" if not errors else "OK_WITH_ERRORS",
            len(classified),
            red_alerts,
            errors,
            source_stats=source_stats,
        )
        return {
            "saved": saved_count,
            "found": len(classified),
            "red_alerts": red_alerts,
            "errors": errors,
            "source_stats": source_stats,
            "sources_total": configured_sources,
            "sources_fetched": sources_attempted,
            "sources_skipped": sources_skipped,
            "sources_skipped_names": sources_skipped_names,
        }
    except Exception as exc:
        errors.append(str(exc))
        database.finish_run(run_id, "FAILED", 0, 0, errors)
        raise
