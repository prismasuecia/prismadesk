from __future__ import annotations

from desk.models import NewsItem
from desk.scoring import temporal_status


def live_temporal_status(row: dict) -> str:
    """Recalculate temporal status for a stored DB row at dashboard render time."""
    item = NewsItem(
        source_name=row.get("source_name") or "",
        source_url=row.get("source_url") or "",
        title=row.get("title") or "",
        summary=row.get("summary") or "",
        content=row.get("content") or "",
        published_at=row.get("published_at"),
        fetched_at=row.get("fetched_at") or "",
        category=row.get("category") or "",
        physical_presence=bool(row.get("physical_presence")),
        accreditation_needed=None
        if row.get("accreditation_needed") is None
        else bool(row.get("accreditation_needed")),
        deadline_detected=bool(row.get("deadline_detected")),
        action_recommendation=row.get("action_recommendation") or "KAN_VÄNTA",
    )
    return temporal_status(item)
