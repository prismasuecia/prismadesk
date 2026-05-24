from __future__ import annotations

import yaml
from dotenv import load_dotenv
from pathlib import Path

from ai.classifier import classify_item
from desk import database
from desk.models import NewsItem
from desk.scoring import stable_item_hash
from feeds.rss_reader import read_rss_source
from feeds.calendar_reader import read_ical_source
from feeds.web_reader import read_web_source
from mail.imap_reader import read_recent_mail
from prisma_site.duplicate_checker import apply_prisma_status, fetch_prisma_articles


BASE_DIR = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_sources() -> list[dict]:
    return load_yaml(BASE_DIR / "config" / "sources.yaml").get("sources", [])


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
    errors: list[str] = []
    all_items: list[NewsItem] = []
    prisma_articles = []

    try:
        site_url = __import__("os").getenv("PRISMA_SITE_URL", "https://www.prismasuecia.se")
        try:
            prisma_articles = fetch_prisma_articles(site_url)
            database.save_prisma_articles(prisma_articles)
        except Exception as exc:
            errors.append(f"Prisma site: {exc}")

        for source in load_sources():
            try:
                all_items.extend(fetch_source(source))
            except Exception as exc:
                errors.append(f"{source.get('name', 'Okänd källa')}: {exc}")

        try:
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
        database.finish_run(run_id, "OK" if not errors else "OK_WITH_ERRORS", len(classified), red_alerts, errors)
        return {"saved": saved_count, "found": len(classified), "red_alerts": red_alerts, "errors": errors}
    except Exception as exc:
        errors.append(str(exc))
        database.finish_run(run_id, "FAILED", 0, 0, errors)
        raise
