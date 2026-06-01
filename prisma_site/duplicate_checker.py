from __future__ import annotations

import re
import os
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from desk.models import NewsItem, PrismaArticle
from feeds.web_reader import HEADERS


STOPWORDS = {
    "och", "eller", "att", "det", "den", "ett", "med", "for", "för", "som",
    "till", "från", "har", "ska", "vid", "por", "para", "con", "una", "los",
    "las", "del", "que", "suecia", "prisma",
}


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-zåäöáéíóúüñ0-9\s-]", " ", text)
    return " ".join(text.split())


def keywords_for(text: str) -> set[str]:
    words = normalize_text(text).split()
    return {word for word in words if len(word) > 3 and word not in STOPWORDS}


def fetch_prisma_articles(site_url: str, limit: int = 40) -> list[PrismaArticle]:
    timeout = int(os.getenv("PRISMA_SITE_TIMEOUT", "6"))
    response = requests.get(site_url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    articles: list[PrismaArticle] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        text = " ".join(link.get_text(" ", strip=True).split())
        if len(text) < 12 or text in seen:
            continue
        seen.add(text)
        url = urljoin(site_url, link["href"])
        if site_url.rstrip("/") not in url:
            continue
        normalized = normalize_text(text)
        articles.append(
            PrismaArticle(
                title=text,
                url=url,
                normalized_title=normalized,
                keywords=", ".join(sorted(keywords_for(text))),
            )
        )
        if len(articles) >= limit:
            break

    return articles


def apply_prisma_status(item: NewsItem, prisma_articles: list[PrismaArticle]) -> NewsItem:
    item_words = keywords_for(item.title + " " + item.summary)
    if not item_words:
        return item

    best_overlap = 0.0
    best_article: PrismaArticle | None = None
    for article in prisma_articles:
        article_words = keywords_for(article.title + " " + article.keywords)
        if not article_words:
            continue
        overlap = len(item_words & article_words) / max(len(item_words), 1)
        if overlap > best_overlap:
            best_overlap = overlap
            best_article = article

    if best_overlap >= 0.7:
        item.already_on_prisma = True
        item.prisma_status = "REDAN_PUBLICERAD"
        item.raw_json["prisma_match"] = best_article.title if best_article else ""
        if item.action_recommendation == "PUBLICERA_IDAG":
            item.action_recommendation = "UPPDATERA_ARTIKEL"
    elif best_overlap >= 0.4:
        item.already_on_prisma = True
        item.prisma_status = "DELVIS_TÄCKT"
        item.raw_json["prisma_match"] = best_article.title if best_article else ""
    elif best_overlap >= 0.25:
        item.prisma_status = "ENDAST_UPPDATERING"
        item.raw_json["prisma_match"] = best_article.title if best_article else ""
    else:
        item.prisma_status = "EJ_PUBLICERAD"

    if item.prisma_status == "REDAN_PUBLICERAD" and item.action_recommendation == "PUBLICERA_IDAG":
        item.action_recommendation = "UPPDATERA_ARTIKEL"

    return item
