from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from desk.models import NewsItem, PrismaArticle, utc_now_iso


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "prisma_desk.sqlite3"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT,
                source_url TEXT,
                title TEXT NOT NULL,
                summary TEXT,
                content TEXT,
                published_at TEXT,
                fetched_at TEXT,
                url TEXT,
                hash TEXT UNIQUE,
                category TEXT,
                priority TEXT,
                desk TEXT,
                physical_presence INTEGER,
                accreditation_needed INTEGER,
                deadline_detected INTEGER,
                deadline_date TEXT,
                already_on_prisma INTEGER,
                prisma_status TEXT,
                action_recommendation TEXT,
                score INTEGER,
                last_seen_run_id INTEGER,
                last_seen_at TEXT,
                raw_json TEXT
            );

            CREATE TABLE IF NOT EXISTS prisma_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT,
                published_at TEXT,
                fetched_at TEXT,
                normalized_title TEXT,
                keywords TEXT,
                UNIQUE(normalized_title, url)
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                finished_at TEXT,
                status TEXT,
                items_found INTEGER DEFAULT 0,
                red_alerts_found INTEGER DEFAULT 0,
                sources_configured INTEGER DEFAULT 0,
                sources_selected INTEGER DEFAULT 0,
                sources_attempted INTEGER DEFAULT 0,
                sources_failed INTEGER DEFAULT 0,
                sources_skipped INTEGER DEFAULT 0,
                errors TEXT
            );
            """
        )
        for statement in [
            "ALTER TABLE items ADD COLUMN last_seen_run_id INTEGER",
            "ALTER TABLE items ADD COLUMN last_seen_at TEXT",
            "ALTER TABLE runs ADD COLUMN sources_configured INTEGER DEFAULT 0",
            "ALTER TABLE runs ADD COLUMN sources_selected INTEGER DEFAULT 0",
            "ALTER TABLE runs ADD COLUMN sources_attempted INTEGER DEFAULT 0",
            "ALTER TABLE runs ADD COLUMN sources_failed INTEGER DEFAULT 0",
            "ALTER TABLE runs ADD COLUMN sources_skipped INTEGER DEFAULT 0",
        ]:
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                pass


def start_run() -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO runs (started_at, status) VALUES (?, ?)",
            (utc_now_iso(), "RUNNING"),
        )
        return int(cursor.lastrowid)


def finish_run(
    run_id: int,
    status: str,
    items_found: int,
    red_alerts_found: int,
    errors: list[str],
    source_stats: dict[str, int] | None = None,
) -> None:
    source_stats = source_stats or {}
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE runs
            SET
                finished_at = ?,
                status = ?,
                items_found = ?,
                red_alerts_found = ?,
                sources_configured = ?,
                sources_selected = ?,
                sources_attempted = ?,
                sources_failed = ?,
                sources_skipped = ?,
                errors = ?
            WHERE id = ?
            """,
            (
                utc_now_iso(),
                status,
                items_found,
                red_alerts_found,
                source_stats.get("configured", 0),
                source_stats.get("selected", 0),
                source_stats.get("attempted", 0),
                source_stats.get("failed", 0),
                source_stats.get("skipped", 0),
                "\n".join(errors),
                run_id,
            ),
        )


def save_prisma_articles(articles: Iterable[PrismaArticle]) -> int:
    saved = 0
    with get_connection() as conn:
        for article in articles:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO prisma_articles
                    (title, url, published_at, fetched_at, normalized_title, keywords)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    article.title,
                    article.url,
                    article.published_at,
                    article.fetched_at,
                    article.normalized_title,
                    article.keywords,
                ),
            )
            saved += cursor.rowcount
    return saved


def save_items(items: Iterable[NewsItem], run_id: int | None = None) -> int:
    saved = 0
    with get_connection() as conn:
        for item in items:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO items (
                    source_name, source_url, title, summary, content, published_at, fetched_at,
                    url, hash, category, priority, desk, physical_presence, accreditation_needed,
                    deadline_detected, deadline_date, already_on_prisma, prisma_status,
                    action_recommendation, score, last_seen_run_id, last_seen_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.source_name,
                    item.source_url,
                    item.title,
                    item.summary,
                    item.content,
                    item.published_at,
                    item.fetched_at,
                    item.url,
                    item.hash,
                    item.category,
                    item.priority,
                    item.desk,
                    int(item.physical_presence),
                    None if item.accreditation_needed is None else int(item.accreditation_needed),
                    int(item.deadline_detected),
                    item.deadline_date,
                    int(item.already_on_prisma),
                    item.prisma_status,
                    item.action_recommendation,
                    item.score,
                    run_id,
                    item.fetched_at,
                    json.dumps(item.raw_json, ensure_ascii=False),
                ),
            )
            saved += cursor.rowcount
            if cursor.rowcount == 0:
                conn.execute(
                    """
                    UPDATE items
                    SET
                        priority = ?,
                        desk = ?,
                        physical_presence = ?,
                        accreditation_needed = ?,
                        deadline_detected = ?,
                        deadline_date = ?,
                        already_on_prisma = ?,
                        prisma_status = ?,
                        action_recommendation = ?,
                        score = ?,
                        last_seen_run_id = ?,
                        last_seen_at = ?,
                        raw_json = ?
                    WHERE hash = ?
                    """,
                    (
                        item.priority,
                        item.desk,
                        int(item.physical_presence),
                        None if item.accreditation_needed is None else int(item.accreditation_needed),
                        int(item.deadline_detected),
                        item.deadline_date,
                        int(item.already_on_prisma),
                        item.prisma_status,
                        item.action_recommendation,
                        item.score,
                        run_id,
                        item.fetched_at,
                        json.dumps(item.raw_json, ensure_ascii=False),
                        item.hash,
                    ),
                )
    return saved


def latest_items(limit: int = 200) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM items
            ORDER BY score DESC, fetched_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def items_since(started_at: str, limit: int = 200) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM items
            WHERE fetched_at >= ?
            ORDER BY score DESC, fetched_at DESC, id DESC
            LIMIT ?
            """,
            (started_at, limit),
        ).fetchall()


def items_for_run(run_id: int, limit: int = 200) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM items
            WHERE last_seen_run_id = ?
            ORDER BY score DESC, last_seen_at DESC, id DESC
            LIMIT ?
            """,
            (run_id, limit),
        ).fetchall()


def latest_run() -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
