"""SQLite storage for Sifu events and sessions."""

import sqlite3
from pathlib import Path
from typing import Optional

SIFU_DIR = Path.home() / ".sifu"
DB_PATH = SIFU_DIR / "capture.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,
    app TEXT,
    window TEXT,
    description TEXT,
    element TEXT,
    position_x INTEGER,
    position_y INTEGER,
    text_content TEXT,
    shortcut TEXT,
    screenshot_path TEXT,
    session_id TEXT,
    workflow_id TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    start_time TEXT,
    end_time TEXT,
    app_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_app ON events(app);
"""


def init_db() -> sqlite3.Connection:
    """Initialize the database, creating tables if needed."""
    SIFU_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def get_connection() -> sqlite3.Connection:
    """Get a database connection, initializing if needed."""
    if not DB_PATH.exists():
        return init_db()
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def insert_event(conn: sqlite3.Connection, event) -> int:
    """Insert an event and return its row ID."""
    d = event.to_dict()
    d.pop("id", None)
    cols = ", ".join(d.keys())
    placeholders = ", ".join("?" for _ in d)
    cursor = conn.execute(
        f"INSERT INTO events ({cols}) VALUES ({placeholders})",
        list(d.values()),
    )
    conn.commit()
    return cursor.lastrowid


def query_events(app=None, last=None, limit=50):
    """Query and display events. Called from CLI."""
    import click
    import re
    from datetime import datetime, timedelta

    conn = get_connection()
    query = "SELECT * FROM events WHERE 1=1"
    params: list = []

    if app:
        query += " AND app = ?"
        params.append(app)
    if last:
        m = re.match(r"(\d+)([hm])", last)
        if m:
            amount, unit = int(m.group(1)), m.group(2)
            seconds = amount * 3600 if unit == "h" else amount * 60
            cutoff = (datetime.now() - timedelta(seconds=seconds)).isoformat()
            query += " AND timestamp > ?"
            params.append(cutoff)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        click.echo("No events found.")
        return

    for row in rows:
        ts = row["timestamp"][11:19] if row["timestamp"] else "?"
        detail = row["description"] or row["text_content"] or row["shortcut"] or ""
        click.echo(f"  {ts}  {row['type']:15s}  {row['app'] or '':20s}  {detail}")


def list_sessions():
    """List work sessions. Called from CLI."""
    import click

    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM sessions ORDER BY start_time DESC LIMIT 20"
    ).fetchall()
    conn.close()

    if not rows:
        click.echo("No sessions found.")
        return
    for row in rows:
        click.echo(f"  {row['id']}  {row['start_time']} — {row['end_time'] or 'active'}")


def create_session(conn: sqlite3.Connection, session_id: str, start_time: str):
    conn.execute(
        "INSERT INTO sessions (id, start_time) VALUES (?, ?)",
        (session_id, start_time),
    )
    conn.commit()


def end_session(conn: sqlite3.Connection, session_id: str, end_time: str, app_summary: str = None):
    conn.execute(
        "UPDATE sessions SET end_time = ?, app_summary = ? WHERE id = ?",
        (end_time, app_summary, session_id),
    )
    conn.commit()


def purge_recent(conn: sqlite3.Connection, minutes: int = 5) -> list[str]:
    """Purge events from the last N minutes. Returns screenshot paths to delete."""
    from datetime import datetime, timedelta

    cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
    rows = conn.execute(
        "SELECT screenshot_path FROM events WHERE timestamp > ? AND screenshot_path IS NOT NULL",
        (cutoff,),
    ).fetchall()
    conn.execute("DELETE FROM events WHERE timestamp > ?", (cutoff,))
    conn.commit()
    return [row["screenshot_path"] for row in rows]


def get_events_between(conn: sqlite3.Connection, start: str, end: str, app: str = None) -> list:
    """Get events in a time range. Returns list of sqlite3.Row."""
    query = "SELECT * FROM events WHERE timestamp BETWEEN ? AND ?"
    params: list = [start, end]
    if app:
        query += " AND app = ?"
        params.append(app)
    query += " ORDER BY timestamp ASC"
    return conn.execute(query, params).fetchall()


def get_events_by_session(conn: sqlite3.Connection, session_id: str) -> list:
    """Get all events for a session."""
    return conn.execute(
        "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,),
    ).fetchall()


def get_events_by_workflow(conn: sqlite3.Connection, workflow_id: str) -> list:
    """Get all events for a workflow segment."""
    return conn.execute(
        "SELECT * FROM events WHERE workflow_id = ? ORDER BY timestamp ASC",
        (workflow_id,),
    ).fetchall()


def update_workflow_id(conn: sqlite3.Connection, event_ids: list[int], workflow_id: str):
    """Assign a workflow ID to a set of events."""
    placeholders = ",".join("?" for _ in event_ids)
    conn.execute(
        f"UPDATE events SET workflow_id = ? WHERE id IN ({placeholders})",
        [workflow_id] + event_ids,
    )
    conn.commit()
