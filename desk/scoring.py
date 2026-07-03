from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from desk.models import NewsItem


PRIORITY_SCORE = {
    "RED": 100,
    "ORANGE": 75,
    "YELLOW": 55,
    "BLUE": 40,
    "GREEN": 30,
    "GREY": 10,
}


ACTION_SCORE = {
    "ÅK_DIT": 30,
    "SÖK_ACKREDITERING": 25,
    "RING_MAILA_NU": 20,
    "PUBLICERA_IDAG": 18,
    "UPPDATERA_ARTIKEL": 12,
    "SOCIAL_REPOST": 8,
    "FÖLJ_UPP": 8,
    "KAN_VÄNTA": 0,
    "IGNORERA": -20,
}

SWEDISH_MONTHS = {
    "januari": 1,
    "februari": 2,
    "mars": 3,
    "april": 4,
    "maj": 5,
    "juni": 6,
    "juli": 7,
    "augusti": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}


def stable_item_hash(item: NewsItem) -> str:
    basis = f"{item.title.strip().lower()}|{item.url.strip().lower()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def detect_deadline(text: str) -> tuple[bool, str | None]:
    cue_pattern = (
        r"\b(deadline|anmälan senast|senast den|senast kl\.?|osa|rsvp|föranmälan|"
        r"ackreditering|ackreditera|anmäl dig|sista anmälningsdag)\b"
    )
    patterns = [
        rf"{cue_pattern}[^\n.]{{0,100}}",
        rf"{cue_pattern}[^\n.]{{0,100}}\b\d{{1,2}}[/-]\d{{1,2}}(?:[/-]\d{{2,4}})?\b",
        rf"{cue_pattern}[^\n.]{{0,100}}\b\d{{1,2}}\s+(?:januari|februari|mars|april|maj|juni|juli|augusti|september|oktober|november|december)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return True, match.group(0).strip()
    return False, None


def hours_until_deadline(deadline_date: str | None, now: datetime | None = None) -> float | None:
    if not deadline_date:
        return None
    now = now or datetime.now(timezone.utc)
    parsed = parse_item_datetime(deadline_date)
    if not parsed:
        return None
    return (parsed.astimezone(now.tzinfo) - now).total_seconds() / 3600


def parse_item_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    numeric_patterns = [
        r"\b(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{1,2})[:.](\d{2}))?\b",
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*(\d{1,2})/(\d{1,2})\s*-\s*(\d{4})(?:\s+(\d{1,2})[:.](\d{2}))?\b",
    ]
    for index, pattern in enumerate(numeric_patterns):
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            if index == 0:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                hour = int(match.group(4) or 12)
                minute = int(match.group(5) or 0)
            else:
                day = int(match.group(1))
                month = int(match.group(2))
                year = int(match.group(3))
                hour = int(match.group(4) or 12)
                minute = int(match.group(5) or 0)
            return datetime(year, month, day, hour, minute, tzinfo=datetime.now().astimezone().tzinfo)
        except ValueError:
            continue
    for parser in (
        lambda raw: datetime.fromisoformat(raw.replace("Z", "+00:00")),
        parsedate_to_datetime,
    ):
        try:
            parsed = parser(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
            return parsed
        except (TypeError, ValueError):
            continue
    return None


def detect_swedish_event_datetime(text: str, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now().astimezone()
    month_names = "|".join(SWEDISH_MONTHS)
    patterns = [
        r"\b(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{1,2})[:.](\d{2}))?\b",
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*(\d{1,2})/(\d{1,2})\s*-\s*(\d{4})(?:\s+(\d{1,2})[:.](\d{2}))?\b",
        rf"(?:måndag|tisdag|onsdag|torsdag|fredag|lördag|söndag)?\s*(?:den\s+)?(\d{{1,2}})\s+({month_names})(?:\s+(\d{{4}}))?(?:\s+kl\.?\s*(\d{{1,2}})[:.](\d{{2}}))?",
        rf"(\d{{1,2}})\s+({month_names})(?:\s+(\d{{4}}))?",
    ]
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        if index == 0:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            hour = int(match.group(4) or 12)
            minute = int(match.group(5) or 0)
        elif index == 1:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))
            hour = int(match.group(4) or 12)
            minute = int(match.group(5) or 0)
        else:
            day = int(match.group(1))
            month = SWEDISH_MONTHS[match.group(2).lower()]
            year = int(match.group(3)) if match.lastindex and match.group(3) else now.year
            hour = int(match.group(4)) if match.lastindex and match.lastindex >= 4 and match.group(4) else 12
            minute = int(match.group(5)) if match.lastindex and match.lastindex >= 5 and match.group(5) else 0
        try:
            candidate = datetime(year, month, day, hour, minute, tzinfo=now.tzinfo)
        except ValueError:
            continue
        if index >= 2 and not match.group(3) and (now - candidate).total_seconds() > 180 * 24 * 3600:
            candidate = candidate.replace(year=year + 1)
        return candidate
    return None


def has_explicit_swedish_event_time(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:kl\.?|klockan)\s*\d{1,2}[:.]\d{2}\b|\b\d{4}-\d{2}-\d{2}[ T]\d{1,2}[:.]\d{2}\b|\b\d{1,2}/\d{1,2}\s*-\s*\d{4}\s+\d{1,2}[:.]\d{2}\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def has_stale_embedded_date(text: str, now: datetime | None = None, max_age_hours: int = 36) -> bool:
    now = now or datetime.now().astimezone()
    embedded_datetime = detect_swedish_event_datetime(text, now)
    if not embedded_datetime:
        return False
    age_hours = (now - embedded_datetime.astimezone(now.tzinfo)).total_seconds() / 3600
    return age_hours > max_age_hours


def has_future_topic_date_context(text: str) -> bool:
    month_names = "|".join(SWEDISH_MONTHS)
    date_pattern = (
        rf"(?:den\s+)?\d{{1,2}}\s+(?:{month_names})|"
        r"\d{4}-\d{2}-\d{2}|"
        r"\d{1,2}/\d{1,2}\s*-\s*\d{4}"
    )
    return bool(re.search(rf"\binför\b[^\n.]{{0,120}}\b(?:toppmöte|möte|ministermöte|besök|konferens)[^\n.]{{0,120}}(?:{date_pattern})", text, flags=re.IGNORECASE))


def effective_item_datetime(item: NewsItem, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now().astimezone()
    event_datetime = detect_swedish_event_datetime(item.text_for_analysis, now)
    published_datetime = parse_item_datetime(item.published_at)
    is_document_source = item.category in {
        "parliament_decisions",
        "parliament_reports",
        "parliament_propositions",
        "parliament_scrutiny",
        "parliament_motions",
    }
    has_event_cue = bool(
        re.search(
            r"\b(pressträff|pressbriefing|presskonferens|pressinbjudan|fototillfälle|pressvisning|möte|besök)\b",
            item.text_for_analysis,
            flags=re.IGNORECASE,
        )
    )
    if published_datetime and event_datetime and event_datetime > now and has_event_cue:
        published_age_hours = (now - published_datetime.astimezone(now.tzinfo)).total_seconds() / 3600
        if (
            published_age_hours > 36
            and not has_explicit_swedish_event_time(item.text_for_analysis)
            and has_future_topic_date_context(item.text_for_analysis)
        ):
            return published_datetime
    if event_datetime and (
        not is_document_source
        and (
            item.physical_presence
            or item.deadline_detected
            or has_event_cue
            or item.action_recommendation in {"ÅK_DIT", "SÖK_ACKREDITERING", "RING_MAILA_NU"}
        )
    ):
        return event_datetime
    return published_datetime


def temporal_status(item: NewsItem, now: datetime | None = None) -> str:
    now = now or datetime.now().astimezone()
    relevant_datetime = effective_item_datetime(item, now)
    if not relevant_datetime:
        return "UNKNOWN"
    age_hours = (now - relevant_datetime.astimezone(now.tzinfo)).total_seconds() / 3600
    is_document_source = item.category in {
        "parliament_decisions",
        "parliament_reports",
        "parliament_propositions",
        "parliament_scrutiny",
        "parliament_motions",
    }
    event_like = not is_document_source and (
        item.physical_presence
        or item.deadline_detected
        or bool(
            re.search(
                r"\b(pressträff|pressbriefing|presskonferens|pressinbjudan|fototillfälle|pressvisning)\b",
                item.text_for_analysis,
                flags=re.IGNORECASE,
            )
        )
        or item.action_recommendation in {
        "ÅK_DIT",
        "SÖK_ACKREDITERING",
        "RING_MAILA_NU",
        }
    )
    event_datetime = detect_swedish_event_datetime(item.text_for_analysis, now)
    if (
        event_like
        and event_datetime
        and not has_explicit_swedish_event_time(item.text_for_analysis)
        and event_datetime.astimezone(now.tzinfo).date() < now.date()
    ):
        return "PAST_EVENT"
    if event_like and age_hours > 36:
        return "PAST_EVENT"
    if event_like and statusless_stale_text(item.text_for_analysis, now):
        return "PAST_EVENT"
    if age_hours > 168:
        return "OLD"
    if age_hours < -1:
        return "UPCOMING"
    return "CURRENT"


def statusless_stale_text(text: str, now: datetime | None = None) -> bool:
    return has_stale_embedded_date(text, now=now, max_age_hours=36)


def apply_temporal_guardrails(item: NewsItem) -> NewsItem:
    status = temporal_status(item)
    item.raw_json["temporal_status"] = status
    is_document_source = item.category in {
        "parliament_decisions",
        "parliament_reports",
        "parliament_propositions",
        "parliament_scrutiny",
        "parliament_motions",
    }
    event_datetime = detect_swedish_event_datetime(item.text_for_analysis)
    if event_datetime and not is_document_source:
        item.raw_json["detected_event_datetime"] = event_datetime.isoformat()

    if is_document_source and status == "OLD":
        if item.priority in {"RED", "ORANGE"}:
            item.priority = "YELLOW"
        if item.desk in {"ZUMA", "BOTH"}:
            item.desk = "PRISMA"
        item.physical_presence = False
        item.accreditation_needed = None
        if item.action_recommendation == "PUBLICERA_IDAG":
            item.action_recommendation = "FÖLJ_UPP"
        item.raw_json.pop("image_suggestions", None)
        item.raw_json.pop("zuma_image_angle", None)
        item.raw_json.pop("access_guidance", None)
        item.raw_json["why_it_matters"] = (
            "Äldre riksdagsdokument. Publicera inte som ny nyhet utan ny utveckling, tydlig Prisma-vinkel eller uppdatering."
        )

    if item.action_recommendation == "ÅK_DIT" and not item.physical_presence:
        item.action_recommendation = "FÖLJ_UPP"
        if item.priority == "RED":
            item.priority = "YELLOW"
        item.raw_json["why_it_matters"] = (
            "Viktig signal, men ingen tydlig fysisk pressträff eller mötestid hittades. Följ upp innan eventuell åtgärd."
        )

    if status == "PAST_EVENT":
        if item.priority == "RED":
            item.priority = "YELLOW"
        if item.action_recommendation in {"ÅK_DIT", "SÖK_ACKREDITERING", "RING_MAILA_NU", "PUBLICERA_IDAG"}:
            item.action_recommendation = "FÖLJ_UPP"
        item.physical_presence = False
        if item.desk in {"ZUMA", "BOTH"}:
            item.desk = "PRISMA" if item.prisma_status != "REDAN_PUBLICERAD" else "IGNORE"
        item.raw_json["why_it_matters"] = (
            "Passerad händelse. Åk inte dit; bedöm om ämnet ska följas upp, uppdateras eller användas som bakgrund."
        )
    elif status == "OLD" and item.action_recommendation == "PUBLICERA_IDAG":
        item.action_recommendation = "FÖLJ_UPP"
        item.raw_json["why_it_matters"] = (
            "Äldre fynd. Publicera inte som nyhet utan ny vinkel eller uppdatering."
        )

    if item.action_recommendation in {"ÅK_DIT", "SÖK_ACKREDITERING"} and status in {"PAST_EVENT", "OLD"}:
        item.action_recommendation = "FÖLJ_UPP"

    return item


def calculate_score(item: NewsItem) -> int:
    score = PRIORITY_SCORE.get(item.priority, 0)
    score += ACTION_SCORE.get(item.action_recommendation, 0)
    if item.desk == "BOTH":
        score += 20
    elif item.desk in {"ZUMA", "PRISMA"}:
        score += 10
    if item.physical_presence:
        score += 12
    stockholm_local_categories = {
        "stockholm_city",
        "stockholm_city_press",
        "media_stockholm",
        "police_stockholm",
        "region_stockholm",
        "arena_stockholm",
        "sport_national_team",
        "culture",
        "events",
        "transport",
    }
    if item.raw_json.get("location_fit") == "STOCKHOLM" and item.physical_presence:
        score += 18
    elif item.raw_json.get("location_fit") == "STOCKHOLM" and item.category in stockholm_local_categories:
        score += 8
    elif item.raw_json.get("location_fit") == "UTANFÖR_STOCKHOLM" and item.physical_presence:
        score -= 10
    if item.accreditation_needed:
        score += 8
    if item.deadline_detected:
        score += 10
    if item.prisma_status == "REDAN_PUBLICERAD":
        score -= 20
    return max(score, 0)
