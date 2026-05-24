from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class NewsItem:
    source_name: str
    source_url: str
    title: str
    summary: str = ""
    content: str = ""
    published_at: str | None = None
    fetched_at: str = field(default_factory=utc_now_iso)
    url: str = ""
    hash: str = ""
    category: str = ""
    priority: str = "GREY"
    desk: str = "IGNORE"
    physical_presence: bool = False
    accreditation_needed: bool | None = None
    deadline_detected: bool = False
    deadline_date: str | None = None
    already_on_prisma: bool = False
    prisma_status: str = "EJ_PUBLICERAD"
    action_recommendation: str = "KAN_VÄNTA"
    score: int = 0
    raw_json: dict[str, Any] = field(default_factory=dict)

    @property
    def text_for_analysis(self) -> str:
        return " ".join(
            part for part in [self.title, self.summary, self.content, self.source_name] if part
        )


@dataclass
class PrismaArticle:
    title: str
    url: str
    published_at: str | None = None
    fetched_at: str = field(default_factory=utc_now_iso)
    normalized_title: str = ""
    keywords: str = ""
