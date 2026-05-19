"""Tests for the canonical workflow library + schema migration."""
import sqlite3
from sifu.storage.db import SCHEMA, migrate_db

FRAME_COLS = {"display_id", "display_bounds", "window_rect", "backing_scale", "url"}

def test_schema_has_frame_columns():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    assert FRAME_COLS.issubset(cols)
    conn.close()

def test_migrate_db_adds_columns_to_old_table():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE events (id INTEGER PRIMARY KEY, timestamp TEXT, type TEXT,
        app TEXT, window TEXT, description TEXT, element TEXT,
        position_x INTEGER, position_y INTEGER, text_content TEXT,
        shortcut TEXT, screenshot_path TEXT, session_id TEXT, workflow_id TEXT);
    """)
    migrate_db(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    assert FRAME_COLS.issubset(cols)
    migrate_db(conn)  # idempotent: must not raise
    conn.close()


from sifu.events import Event, EventType


def test_event_roundtrips_frame_fields():
    e = Event(
        type=EventType.CLICK, app="Google Chrome",
        position_x=840, position_y=312,
        display_id=1, display_bounds="[0,0,1920,1080]",
        window_rect="[120,80,1280,800]", backing_scale=2.0,
        url="https://app.stripe.com/cart",
    )
    d = e.to_dict()
    assert d["display_id"] == 1
    assert d["url"] == "https://app.stripe.com/cart"
    e2 = Event.from_dict(d)
    assert e2.backing_scale == 2.0
    assert e2.window_rect == "[120,80,1280,800]"
