from __future__ import annotations

import yaml
import os
import time
from dotenv import load_dotenv
from pathlib import Path

from ai.classifier import classify_item
from desk import database
from desk.models import NewsItem
from desk.scoring import stable_item_hash
from feeds.rss_reader import read_rss_source
from feeds.calendar_reader import read_ical_source
from feeds.web_reader import read_web_source
from prisma_site.duplicate_checker import apply_prisma_status, fetch_prisma_articles


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_PRIORITY_ORDER = {
    "red": 0,
    "orange": 1,
    "yellow": 2,
    "blue": 3,
    "green": 4,
}


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


def count_configured_sources() -> int:
    return len(load_yaml(BASE_DIR / "config" / "sources.yaml").get("sources", []))


def fetch_source(source: dict) -> list[NewsItem]:
    if source.get("type") == "rss":
        return read_rss_source(source)
    if source.get("type") == "ical":
        return read_ical_source(source)
    return read_web_source(source)


def run_update() -> dict:
    load_dotenv(BASE_DIR / ".env")
    database.init_db()
    run_id = database.start_run()
    started = time.monotonic()
    max_seconds = float(os.getenv("PRISMA_UPDATE_MAX_SECONDS", "0") or "0")
    errors: list[str] = []
    all_items: list[NewsItem] = []
    prisma_articles = []
    configured_sources = count_configured_sources()
    selected_sources = load_sources()
    sources_attempted = 0
    sources_failed = 0
    sources_skipped = max(configured_sources - len(selected_sources), 0)

    try:
        site_url = __import__("os").getenv("PRISMA_SITE_URL", "https://www.prismasuecia.se")
        try:
            prisma_articles = fetch_prisma_articles(site_url)
            database.save_prisma_articles(prisma_articles)
        except Exception as exc:
            errors.append(f"Prisma site: {exc}")

        for source in selected_sources:
            if max_seconds and time.monotonic() - started > max_seconds:
                errors.append(
                    f"Tidsbudget nådd efter {int(max_seconds)} sekunder. Kör igen för fler källor."
                )
                sources_skipped += max(len(selected_sources) - sources_attempted, 0)
                break
            sources_attempted += 1
            try:
                all_items.extend(fetch_source(source))
            except Exception as exc:
                sources_failed += 1
                errors.append(f"{source.get('name', 'Okänd källa')}: {exc}")

        if os.getenv("ENABLE_MAIL", "false").lower() == "true":
            try:
                from mail.imap_reader import read_recent_mail

                all_items.extend(read_recent_mail())
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
        red_alerts = sum(1 for item in classified if item.priority == "RED")
        source_stats = {
            "configured": configured_sources,
            "selected": len(selected_sources),
            "attempted": sources_attempted,
            "failed": sources_failed,
            "skipped": sources_skipped,
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
        }
    except Exception as exc:
        errors.append(str(exc))
        database.finish_run(run_id, "FAILED", 0, 0, errors)
        raise
