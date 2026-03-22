import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "tdb.sqlite"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS commands (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                command   TEXT NOT NULL,
                tags      TEXT NOT NULL DEFAULT '[]',
                purpose   TEXT NOT NULL DEFAULT '',
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()


def insert_command(command: str, tags: list[str], purpose: str) -> int:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO commands (command, tags, purpose, timestamp) VALUES (?, ?, ?, ?)",
            (command, json.dumps(tags), purpose, now),
        )
        conn.commit()
        return cur.lastrowid


def fetch_all() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM commands ORDER BY timestamp DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_by_id(record_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM commands WHERE id = ?", (record_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_by_id(record_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM commands WHERE id = ?", (record_id,))
        conn.commit()
        return cur.rowcount > 0


def search_local(query: str) -> list[dict]:
    """
    Tiered local search: prioritise matches in command text and tags over purpose.
    Returns results ordered by relevance tier then recency.
    """
    q = f"%{query.lower()}%"
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *, CASE
              WHEN lower(command) LIKE ? THEN 1
              WHEN lower(tags)    LIKE ? THEN 2
              WHEN lower(purpose) LIKE ? THEN 3
              ELSE 4
            END AS tier
            FROM commands
            WHERE lower(command) LIKE ?
               OR lower(tags)    LIKE ?
               OR lower(purpose) LIKE ?
            ORDER BY tier ASC, timestamp DESC
            """,
            (q, q, q, q, q, q),
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_all_for_search() -> list[dict]:
    """Return all records for AI-assisted search ranking."""
    return fetch_all()


def find_duplicate(command: str) -> dict | None:
    """Return existing record if an identical command already exists."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM commands WHERE command = ?", (command,)
        ).fetchone()
    return dict(row) if row else None
