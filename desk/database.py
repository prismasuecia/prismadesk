from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
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
                cluster_id INTEGER,
                dismissed INTEGER DEFAULT 0,
                dismissed_at TEXT,
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
                sources_total INTEGER DEFAULT 0,
                sources_fetched INTEGER DEFAULT 0,
                sources_skipped_names TEXT,
                errors TEXT
            );

            CREATE TABLE IF NOT EXISTS story_clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_key TEXT UNIQUE,
                primary_item_id INTEGER,
                member_item_ids TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS view_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_viewed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS item_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                feedback_type TEXT NOT NULL,
                note TEXT,
                created_at TEXT,
                original_priority TEXT,
                original_score INTEGER
            );

            CREATE TABLE IF NOT EXISTS source_health (
                source_name TEXT PRIMARY KEY,
                consecutive_zero_runs INTEGER DEFAULT 0,
                last_success_at TEXT,
                last_checked_at TEXT
            );

            INSERT OR IGNORE INTO view_state (id, last_viewed_at) VALUES (1, NULL);
            """
        )
        for statement in [
            "ALTER TABLE items ADD COLUMN last_seen_run_id INTEGER",
            "ALTER TABLE items ADD COLUMN last_seen_at TEXT",
            "ALTER TABLE items ADD COLUMN cluster_id INTEGER",
            "ALTER TABLE items ADD COLUMN dismissed INTEGER DEFAULT 0",
            "ALTER TABLE items ADD COLUMN dismissed_at TEXT",
            "ALTER TABLE runs ADD COLUMN sources_configured INTEGER DEFAULT 0",
            "ALTER TABLE runs ADD COLUMN sources_selected INTEGER DEFAULT 0",
            "ALTER TABLE runs ADD COLUMN sources_attempted INTEGER DEFAULT 0",
            "ALTER TABLE runs ADD COLUMN sources_failed INTEGER DEFAULT 0",
            "ALTER TABLE runs ADD COLUMN sources_skipped INTEGER DEFAULT 0",
            "ALTER TABLE runs ADD COLUMN sources_total INTEGER DEFAULT 0",
            "ALTER TABLE runs ADD COLUMN sources_fetched INTEGER DEFAULT 0",
            "ALTER TABLE runs ADD COLUMN sources_skipped_names TEXT",
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
                sources_total = ?,
                sources_fetched = ?,
                sources_skipped_names = ?,
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
                source_stats.get("configured", 0),
                source_stats.get("attempted", 0),
                json.dumps(source_stats.get("skipped_names", []), ensure_ascii=False),
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


def latest_items(limit: int = 200, include_dismissed: bool = False) -> list[sqlite3.Row]:
    where_clause = "" if include_dismissed else "WHERE COALESCE(dismissed, 0) = 0"
    with get_connection() as conn:
        return conn.execute(
            f"""
            SELECT * FROM items
            {where_clause}
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


def items_for_run(run_id: int, limit: int = 200, include_dismissed: bool = False) -> list[sqlite3.Row]:
    dismissed_clause = "" if include_dismissed else "AND COALESCE(dismissed, 0) = 0"
    with get_connection() as conn:
        return conn.execute(
            f"""
            SELECT * FROM items
            WHERE last_seen_run_id = ?
            {dismissed_clause}
            ORDER BY score DESC, last_seen_at DESC, id DESC
            LIMIT ?
            """,
            (run_id, limit),
        ).fetchall()


def items_in_window(hours: int = 72) -> list[sqlite3.Row]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM items
            WHERE fetched_at >= ?
            ORDER BY score DESC, fetched_at DESC, id DESC
            """,
            (cutoff,),
        ).fetchall()


def save_cluster(cluster_key: str, item_ids: list[int]) -> None:
    if not item_ids:
        return
    with get_connection() as conn:
        placeholders = ",".join("?" for _ in item_ids)
        rows = conn.execute(
            f"SELECT id, score FROM items WHERE id IN ({placeholders}) ORDER BY score DESC, id DESC",
            item_ids,
        ).fetchall()
        if not rows:
            return
        sorted_ids = [int(row["id"]) for row in rows]
        primary_id = sorted_ids[0]
        now = utc_now_iso()
        conn.execute(
            """
            INSERT INTO story_clusters
                (cluster_key, primary_item_id, member_item_ids, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(cluster_key) DO UPDATE SET
                primary_item_id = excluded.primary_item_id,
                member_item_ids = excluded.member_item_ids,
                updated_at = excluded.updated_at
            """,
            (cluster_key, primary_id, json.dumps(sorted_ids), now, now),
        )
        cluster_row = conn.execute(
            "SELECT id FROM story_clusters WHERE cluster_key = ?",
            (cluster_key,),
        ).fetchone()
        if not cluster_row:
            return
        conn.executemany(
            "UPDATE items SET cluster_id = ? WHERE id = ?",
            [(cluster_row["id"], item_id) for item_id in sorted_ids],
        )


def enrich_with_cluster_info(items: list[dict]) -> list[dict]:
    cluster_ids = sorted({item.get("cluster_id") for item in items if item.get("cluster_id")})
    if not cluster_ids:
        for item in items:
            item["cluster_is_primary"] = True
            item["cluster_size"] = 1
            item["cluster_other_sources"] = []
        return items

    placeholders = ",".join("?" for _ in cluster_ids)
    with get_connection() as conn:
        cluster_rows = conn.execute(
            f"SELECT * FROM story_clusters WHERE id IN ({placeholders})",
            cluster_ids,
        ).fetchall()
        clusters = {row["id"]: row for row in cluster_rows}
        member_ids = set()
        for row in cluster_rows:
            member_ids.update(json.loads(row["member_item_ids"] or "[]"))

        member_sources: dict[int, str] = {}
        if member_ids:
            member_placeholders = ",".join("?" for _ in member_ids)
            rows = conn.execute(
                f"SELECT id, source_name FROM items WHERE id IN ({member_placeholders})",
                sorted(member_ids),
            ).fetchall()
            member_sources = {int(row["id"]): row["source_name"] for row in rows}

    for item in items:
        cluster = clusters.get(item.get("cluster_id"))
        if not cluster:
            item["cluster_is_primary"] = True
            item["cluster_size"] = 1
            item["cluster_other_sources"] = []
            continue
        member_ids = json.loads(cluster["member_item_ids"] or "[]")
        item["cluster_is_primary"] = int(item["id"]) == int(cluster["primary_item_id"])
        item["cluster_size"] = len(member_ids)
        item["cluster_other_sources"] = [
            member_sources.get(member_id, "Okänd källa")
            for member_id in member_ids
            if member_id != item["id"]
        ]
    return items


def latest_run() -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()


def mark_stale_running_runs(max_age_minutes: int = 10) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)).isoformat(
        timespec="seconds"
    )
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE runs
            SET
                finished_at = ?,
                status = 'FAILED',
                errors = COALESCE(NULLIF(errors, ''), 'Körningen avbröts innan den hann avslutas.')
            WHERE status = 'RUNNING'
              AND started_at < ?
            """,
            (utc_now_iso(), cutoff),
        )
        return int(cursor.rowcount)


def get_last_viewed_at() -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT last_viewed_at FROM view_state WHERE id = 1").fetchone()
        return row["last_viewed_at"] if row else None


def mark_viewed_now() -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE view_state SET last_viewed_at = ? WHERE id = 1",
            (utc_now_iso(),),
        )


def dismiss_item(item_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE items SET dismissed = 1, dismissed_at = ? WHERE id = ?",
            (utc_now_iso(), item_id),
        )


def record_feedback(item_id: int, feedback_type: str, note: str = "") -> None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT priority, score FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO item_feedback
                (item_id, feedback_type, note, created_at, original_priority, original_score)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                feedback_type,
                note,
                utc_now_iso(),
                row["priority"] if row else None,
                row["score"] if row else None,
            ),
        )


def feedback_summary() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT feedback_type, original_priority, COUNT(*) AS n
            FROM item_feedback
            GROUP BY feedback_type, original_priority
            ORDER BY n DESC
            """
        ).fetchall()


def update_source_health(source_name: str, item_count: int) -> None:
    now = utc_now_iso()
    with get_connection() as conn:
        if item_count > 0:
            conn.execute(
                """
                INSERT INTO source_health
                    (source_name, consecutive_zero_runs, last_success_at, last_checked_at)
                VALUES (?, 0, ?, ?)
                ON CONFLICT(source_name) DO UPDATE SET
                    consecutive_zero_runs = 0,
                    last_success_at = excluded.last_success_at,
                    last_checked_at = excluded.last_checked_at
                """,
                (source_name, now, now),
            )
        else:
            conn.execute(
                """
                INSERT INTO source_health
                    (source_name, consecutive_zero_runs, last_checked_at)
                VALUES (?, 1, ?)
                ON CONFLICT(source_name) DO UPDATE SET
                    consecutive_zero_runs = consecutive_zero_runs + 1,
                    last_checked_at = excluded.last_checked_at
                """,
                (source_name, now),
            )


def source_health_rows() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM source_health
            ORDER BY consecutive_zero_runs DESC, last_checked_at DESC, source_name
            """
        ).fetchall()
