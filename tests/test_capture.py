"""Tests for Sifu capture modules (Layer 0)."""

import sqlite3
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from sifu.events import Event, EventType, TERMINAL_APPS, IGNORE_APPS_DEFAULT
from sifu.storage.db import init_db, insert_event, get_connection


# ── Event model tests ────────────────────────────────────


class TestEvent:
    def test_create_click_event(self):
        e = Event(type=EventType.CLICK, app="Chrome", position_x=100, position_y=200)
        assert e.type == EventType.CLICK
        assert e.app == "Chrome"
        assert e.position_x == 100

    def test_to_dict(self):
        e = Event(type=EventType.SHORTCUT, shortcut="Cmd+C", app="Ghostty")
        d = e.to_dict()
        assert d["type"] == "shortcut"
        assert d["shortcut"] == "Cmd+C"

    def test_to_json_roundtrip(self):
        e = Event(type=EventType.COMMAND, text_content="git status", app="Ghostty")
        j = e.to_json()
        d = json.loads(j)
        e2 = Event.from_dict(d)
        assert e2.type == EventType.COMMAND
        assert e2.text_content == "git status"

    def test_event_types(self):
        assert EventType.CLICK.value == "click"
        assert EventType.RIGHT_CLICK.value == "right_click"
        assert EventType.SHORTCUT.value == "shortcut"
        assert EventType.TEXT_INPUT.value == "text_input"
        assert EventType.COMMAND.value == "command"
        assert EventType.APP_SWITCH.value == "app_switch"
        assert EventType.WINDOW_SWITCH.value == "window_switch"

    def test_terminal_apps_defined(self):
        assert "Ghostty" in TERMINAL_APPS
        assert "Terminal" in TERMINAL_APPS
        assert "iTerm2" in TERMINAL_APPS

    def test_ignore_apps_default(self):
        assert "1Password" in IGNORE_APPS_DEFAULT
        assert "Bitwarden" in IGNORE_APPS_DEFAULT


# ── SQLite tests ─────────────────────────────────────────


class TestDatabase:
    def setup_method(self):
        """Create an in-memory database for each test."""
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        from sifu.storage.db import SCHEMA
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def teardown_method(self):
        self.conn.close()

    def test_schema_creates_tables(self):
        tables = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {t["name"] for t in tables}
        assert "events" in names
        assert "sessions" in names

    def test_insert_and_query_event(self):
        e = Event(
            type=EventType.CLICK,
            app="Chrome",
            window="Google",
            position_x=100,
            position_y=200,
            session_id="test-session",
        )
        row_id = insert_event(self.conn, e)
        assert row_id > 0

        row = self.conn.execute("SELECT * FROM events WHERE id = ?", (row_id,)).fetchone()
        assert row["type"] == "click"
        assert row["app"] == "Chrome"
        assert row["position_x"] == 100

    def test_insert_multiple_events(self):
        for i in range(5):
            e = Event(type=EventType.CLICK, app=f"App{i}", session_id="s1")
            insert_event(self.conn, e)

        count = self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert count == 5

    def test_session_create_and_end(self):
        from sifu.storage.db import create_session, end_session

        create_session(self.conn, "s-001", "2026-03-31T10:00:00")
        row = self.conn.execute("SELECT * FROM sessions WHERE id = ?", ("s-001",)).fetchone()
        assert row["start_time"] == "2026-03-31T10:00:00"
        assert row["end_time"] is None

        end_session(self.conn, "s-001", "2026-03-31T11:00:00", '{"Chrome": 3600}')
        row = self.conn.execute("SELECT * FROM sessions WHERE id = ?", ("s-001",)).fetchone()
        assert row["end_time"] == "2026-03-31T11:00:00"

    def test_purge_recent(self):
        from sifu.storage.db import purge_recent

        # Insert an event with current timestamp
        e = Event(type=EventType.CLICK, app="Chrome", screenshot_path="/tmp/test.jpg")
        insert_event(self.conn, e)

        paths = purge_recent(self.conn, minutes=5)
        assert "/tmp/test.jpg" in paths

        count = self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert count == 0

    def test_get_events_between(self):
        from sifu.storage.db import get_events_between

        e1 = Event(type=EventType.CLICK, app="Chrome")
        e1.timestamp = "2026-03-31T10:00:00"
        e2 = Event(type=EventType.CLICK, app="Safari")
        e2.timestamp = "2026-03-31T12:00:00"

        insert_event(self.conn, e1)
        insert_event(self.conn, e2)

        rows = get_events_between(self.conn, "2026-03-31T09:00:00", "2026-03-31T11:00:00")
        assert len(rows) == 1
        assert rows[0]["app"] == "Chrome"

    def test_update_workflow_id(self):
        from sifu.storage.db import update_workflow_id

        e = Event(type=EventType.CLICK, app="Chrome")
        eid = insert_event(self.conn, e)

        update_workflow_id(self.conn, [eid], "wf-001")
        row = self.conn.execute("SELECT workflow_id FROM events WHERE id = ?", (eid,)).fetchone()
        assert row["workflow_id"] == "wf-001"


# ── Config tests ─────────────────────────────────────────


class TestConfig:
    def test_default_config_keys(self):
        from sifu.config import DEFAULT_CONFIG

        assert "screenshot_budget_mb" in DEFAULT_CONFIG
        assert "ignore_apps" in DEFAULT_CONFIG
        assert "sensitive_purge_minutes" in DEFAULT_CONFIG

    def test_load_config_returns_defaults(self):
        from sifu.config import load_config

        config = load_config()
        assert config["screenshot_budget_mb"] == 1024
        assert "1Password" in config["ignore_apps"]

    def test_set_and_get(self):
        from sifu.config import set_value, get

        set_value("screenshot_quality", "90")
        assert get("screenshot_quality") == 90


# ── Disk storage tests ───────────────────────────────────


class TestDisk:
    def test_get_screenshot_path_format(self):
        from sifu.storage.disk import get_screenshot_path

        path = get_screenshot_path()
        assert path.suffix == ".jpg"
        assert ".sifu/screenshots/" in str(path)


# ── Screenshot dedup tests ───────────────────────────────


class TestScreenshotDedup:
    def test_skips_text_input(self):
        from sifu.capture.screenshots import ScreenshotCapture

        sc = ScreenshotCapture({"screenshot_min_interval_s": 2.0})
        e = Event(type=EventType.TEXT_INPUT, app="Chrome")
        assert sc._should_capture(e) is False

    def test_allows_first_click(self):
        from sifu.capture.screenshots import ScreenshotCapture

        sc = ScreenshotCapture({"screenshot_min_interval_s": 2.0})
        e = Event(type=EventType.CLICK, app="Chrome", window="Tab 1")
        assert sc._should_capture(e) is True

    def test_dedup_same_app_window(self):
        from sifu.capture.screenshots import ScreenshotCapture

        sc = ScreenshotCapture({"screenshot_min_interval_s": 2.0})
        e = Event(type=EventType.CLICK, app="Chrome", window="Tab 1")

        # Simulate a recent capture
        sc._last_app = "Chrome"
        sc._last_window = "Tab 1"
        sc._last_time = time.time()

        assert sc._should_capture(e) is False

    def test_allows_different_window(self):
        from sifu.capture.screenshots import ScreenshotCapture

        sc = ScreenshotCapture({"screenshot_min_interval_s": 2.0})
        e = Event(type=EventType.CLICK, app="Chrome", window="Tab 2")

        sc._last_app = "Chrome"
        sc._last_window = "Tab 1"
        sc._last_time = time.time()

        assert sc._should_capture(e) is True
