import feedparser

from desk.models import NewsItem


def read_rss_source(source: dict) -> list[NewsItem]:
    parsed = feedparser.parse(source["url"])
    items: list[NewsItem] = []

    for entry in parsed.entries[:20]:
        items.append(
            NewsItem(
                source_name=source["name"],
                source_url=source["url"],
                title=getattr(entry, "title", "").strip(),
                summary=getattr(entry, "summary", "").strip(),
                content=getattr(entry, "summary", "").strip(),
                published_at=getattr(entry, "published", None),
                url=getattr(entry, "link", ""),
                category=source.get("category", ""),
                raw_json={"source_type": "rss"},
            )
        )

    return [item for item in items if item.title]
