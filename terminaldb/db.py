"""SQLite persistence layer for terminalDB."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

_DB_DIR = Path.home() / ".terminaldb"
DB_PATH = _DB_DIR / "tdb.sqlite"


def _connect() -> sqlite3.Connection:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _connect() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS commands (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                command   TEXT    NOT NULL,
                tags      TEXT    NOT NULL DEFAULT '[]',
                purpose   TEXT    NOT NULL DEFAULT '',
                timestamp TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
            """
        )


def insert_command(command: str, tags: list[str], purpose: str) -> int:
    with _connect() as con:
        cur = con.execute(
            "INSERT INTO commands (command, tags, purpose) VALUES (?, ?, ?)",
            (command, json.dumps(tags), purpose),
        )
        return cur.lastrowid  # type: ignore[return-value]


def fetch_all() -> list[dict]:
    with _connect() as con:
        rows = con.execute(
            "SELECT id, command, tags, purpose, timestamp FROM commands ORDER BY id DESC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def fetch_by_id(record_id: int) -> dict | None:
    with _connect() as con:
        row = con.execute(
            "SELECT id, command, tags, purpose, timestamp FROM commands WHERE id = ?",
            (record_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def delete_by_id(record_id: int) -> bool:
    with _connect() as con:
        cur = con.execute("DELETE FROM commands WHERE id = ?", (record_id,))
        return cur.rowcount > 0


def find_duplicate(command: str) -> dict | None:
    with _connect() as con:
        row = con.execute(
            "SELECT id, command, tags, purpose, timestamp FROM commands WHERE command = ? LIMIT 1",
            (command,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def search_local(query: str) -> list[dict]:
    """Tiered text search: exact command > tag match > purpose/command substring."""
    q = query.lower()
    all_records = fetch_all()
    exact, tag_match, fuzzy = [], [], []

    for r in all_records:
        tags = [t.lower() for t in json.loads(r["tags"])]
        cmd  = r["command"].lower()
        purp = r["purpose"].lower()

        if q == cmd:
            exact.append(r)
        elif q in tags or any(q in t for t in tags):
            tag_match.append(r)
        elif q in cmd or q in purp:
            fuzzy.append(r)

    seen, out = set(), []
    for r in exact + tag_match + fuzzy:
        if r["id"] not in seen:
            seen.add(r["id"])
            out.append(r)
    return out


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if isinstance(d.get("tags"), str):
        try:
            d["tags"] = json.loads(d["tags"])
        except json.JSONDecodeError:
            d["tags"] = []
    return d
