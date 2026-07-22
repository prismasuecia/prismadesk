from urllib.parse import urljoin
import os
import re
from typing import Optional, Tuple

import requests
from bs4 import BeautifulSoup

from desk.models import NewsItem


HEADERS = {
    "User-Agent": "PrismaDesk/0.1 (+manual newsroom research; contact: Prisma Suecia)"
}

GENERIC_TITLE_PARTS = {
    "facebook",
    "instagram",
    "linkedin",
    "youtube",
    "sociala medier",
    "cookies",
    "kontakt",
    "presskontakt",
    "om webbplatsen",
    "till toppen",
    "meny",
    "sök",
    "search",
    "nyhetsrum",
    "allt om",
    "prenumerera",
    "hoppa till",
    "tipsa oss",
    "engelska",
    "min lista",
    "klicka här",
    "se alla",
    "nuvarande",
    "calendario cultural",
    "actividades culturales",
    "actividades anteriores",
    "próximas actividades",
    "proximas actividades",
    "programación del mes",
    "programacion del mes",
    "información general",
    "informacion general",
}

GENERIC_TITLES = {
    "aktuellt",
    "evenemang",
    "news",
    "pressmeddelanden - regeringen.se",
    "sveriges regering - regeringen.se",
    "press- och nyhetsrum | stockholm arlanda airport",
}

GOOD_URL_PARTS = (
    "/pressmeddelanden/",
    "/ud-avrader/",
    "/nyheter/",
    "/aktuellt/",
    "/kalender",
    "/kalendariet",
    "/event",
    "/news-and-events/",
    "/pressrum/",
    "/fichas",
    "/cultura",
    "via.tt.se/pressmeddelande",
)


def _clean(text: str) -> str:
    return " ".join(text.split())


def _fix_mojibake(text: str) -> str:
    if "Ã" not in text and "Â" not in text:
        return text
    try:
        return text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text


def _trim_regeringen_detail_text(text: str) -> str:
    for marker in (
        " Dela Facebook",
        " Sidan är uppmärkt med följande kategorier",
        " Relaterat ",
    ):
        if marker in text:
            text = text.split(marker, 1)[0]
    return text.strip()


def _is_probably_content(title: str, href: str) -> bool:
    lowered = title.lower()
    if lowered in GENERIC_TITLES:
        return False
    if len(title) < 8 or len(title) > 180:
        return False
    if any(part in lowered for part in GENERIC_TITLE_PARTS):
        return False
    if href.startswith("mailto:") or href.startswith("tel:"):
        return False
    if "#" in href and href.split("#", 1)[0].rstrip("/") == "":
        return False
    if href.endswith("#main") or href.endswith("#site-body") or href.endswith("#tipsa"):
        return False
    if any(part in href.lower() for part in GOOD_URL_PARTS):
        return True
    # Let strong date-like titles through even when the URL is not descriptive.
    return bool(re.search(r"\b(20\d{2}|\d{1,2}\s+[a-zåäö]+)\b", lowered))


def _read_regeringen_detail(url: str, timeout: int) -> Tuple[str, Optional[str]]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        return "", None

    if not response.encoding or response.encoding.lower() in {"iso-8859-1", "latin-1"}:
        response.encoding = response.apparent_encoding or "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")
    main = soup.find("main") or soup
    text = _trim_regeringen_detail_text(_clean(main.get_text(" ", strip=True)))
    date_match = re.search(
        r"Publicerad\s+(\d{1,2}\s+[a-zåäö]+\s+\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    return text[:3500], date_match.group(1).strip() if date_match else None


def _should_fetch_regeringen_detail(title: str, context: str, already_found: int) -> bool:
    text = f"{title} {context}".lower()
    if already_found < 6:
        return True
    return bool(
        re.search(
            r"\b(pressträff|pressbriefing|presskonferens|pressinbjudan|bjuder\s+in|"
            r"media\s+bjuds\s+in|föranmälan|ackreditering|rosenbad)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _read_regeringen_source(source: dict, soup: BeautifulSoup, timeout: int) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen: set[str] = set()
    detail_timeout = max(1, min(timeout, int(os.getenv("PRISMA_REGERINGEN_DETAIL_TIMEOUT", "3"))))

    for link in soup.find_all("a", href=True):
        href = urljoin(source["url"], link["href"])
        if "/pressmeddelanden/20" not in href or href in seen:
            continue

        title = _clean(link.get_text(" ", strip=True))
        if len(title) < 8:
            continue

        container = link.find_parent("li") or link.find_parent("div")
        context = _clean(container.get_text(" ", strip=True)) if container else title
        date_match = re.search(r"Publicerad\s+([^·]+)", context)
        detail_text = ""
        detail_date = None
        if _should_fetch_regeringen_detail(title, context, len(items)):
            detail_text, detail_date = _read_regeringen_detail(href, detail_timeout)
        full_context = detail_text or context

        items.append(
            NewsItem(
                source_name=source["name"],
                source_url=source["url"],
                title=title,
                summary=full_context[:800],
                content=full_context,
                published_at=detail_date or (date_match.group(1).strip() if date_match else None),
                url=href,
                category=source.get("category", ""),
                raw_json={"source_type": "web_regeringen", "detail_fetched": bool(detail_text)},
            )
        )
        seen.add(href)
        if len(items) >= 25:
            break

    return items


def _read_regeringen_ud_advisory_source(source: dict, soup: BeautifulSoup, timeout: int) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen: set[str] = set()
    detail_timeout = max(1, min(timeout, int(os.getenv("PRISMA_REGERINGEN_DETAIL_TIMEOUT", "3"))))
    base_url = source["url"].rstrip("/") + "/"

    for link in soup.find_all("a", href=True):
        href = urljoin(source["url"], link["href"])
        normalized_href = href.rstrip("/") + "/"
        if "/ud-avrader/" not in href or normalized_href == base_url or href in seen:
            continue

        title = _clean(link.get_text(" ", strip=True))
        if len(title) < 8 or "avrådan" not in title.lower():
            continue

        container = link.find_parent("li") or link.find_parent("div") or link.find_parent("section")
        context = _clean(container.get_text(" ", strip=True)) if container else title
        date_match = re.search(r"Publicerad\s+([^·]+)", context)
        detail_text, detail_date = _read_regeringen_detail(href, detail_timeout)
        full_context = detail_text or context

        items.append(
            NewsItem(
                source_name=source["name"],
                source_url=source["url"],
                title=title,
                summary=full_context[:800],
                content=full_context,
                published_at=detail_date or (date_match.group(1).strip() if date_match else None),
                url=href,
                category=source.get("category", ""),
                raw_json={
                    "source_type": "web_regeringen_ud_advisory",
                    "detail_fetched": bool(detail_text),
                },
            )
        )
        seen.add(href)
        if len(items) >= 30:
            break

    return items


def read_web_source(source: dict, timeout: Optional[int] = None) -> list[NewsItem]:
    timeout = timeout or int(os.getenv("PRISMA_WEB_TIMEOUT", "8"))
    response = requests.get(source["url"], headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() in {"iso-8859-1", "latin-1"}:
        response.encoding = response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    if "regeringen.se" in source["url"] and "/ud-avrader" in source["url"]:
        return _read_regeringen_ud_advisory_source(source, soup, timeout)
    if "regeringen.se" in source["url"]:
        return _read_regeringen_source(source, soup, timeout)

    candidates: list[NewsItem] = []
    seen: set[str] = set()

    for element in soup.select("main article, main li, main .teaser, main .card, main .news-item, main .pressrelease, article, .teaser, .card, .news-item, .pressrelease")[:90]:
        link = element.find("a", href=True)
        if not link:
            continue

        title_el = element.find(["h1", "h2", "h3", "h4"]) or link
        title = _fix_mojibake(_clean(title_el.get_text(" ", strip=True)))

        href = urljoin(source["url"], link["href"])
        if not _is_probably_content(title, href):
            continue
        if href in seen:
            continue
        seen.add(href)

        time_el = element.find("time")
        summary_el = element.find("p")
        summary = _fix_mojibake(_clean(summary_el.get_text(" ", strip=True))) if summary_el else ""
        published_at = time_el.get("datetime") or _clean(time_el.get_text(" ", strip=True)) if time_el else None

        candidates.append(
            NewsItem(
                source_name=source["name"],
                source_url=source["url"],
                title=title,
                summary=summary,
                content=_fix_mojibake(_clean(element.get_text(" ", strip=True)))[:2200],
                published_at=published_at,
                url=href,
                category=source.get("category", ""),
                raw_json={"source_type": "web"},
            )
        )

    if candidates:
        return candidates[:20]

    for link in soup.find_all("a", href=True)[:300]:
        title = _fix_mojibake(_clean(link.get_text(" ", strip=True)))
        href = urljoin(source["url"], link["href"])
        if not _is_probably_content(title, href):
            continue
        if href in seen:
            continue
        seen.add(href)

        container = link.find_parent(["article", "li", "div", "section"])
        context = _fix_mojibake(_clean(container.get_text(" ", strip=True))) if container else title
        time_el = container.find("time") if container else None
        published_at = time_el.get("datetime") or _clean(time_el.get_text(" ", strip=True)) if time_el else None

        candidates.append(
            NewsItem(
                source_name=source["name"],
                source_url=source["url"],
                title=title,
                summary=context[:500] if context != title else "",
                content=context[:2200],
                published_at=published_at,
                url=href,
                category=source.get("category", ""),
                raw_json={"source_type": "web_fallback"},
            )
        )
        if len(candidates) >= 20:
            break

    return candidates[:20]
