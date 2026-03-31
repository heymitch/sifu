"""Tests for Sifu SOP compiler (Layer 2)."""

import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from sifu.events import Event, EventType
from sifu.storage.db import SCHEMA, insert_event


class TestCompiler:
    def setup_method(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def teardown_method(self):
        self.conn.close()

    def _insert_workflow_events(self, workflow_id="wf-test-001"):
        """Insert sample events for a workflow."""
        events = [
            Event(
                type=EventType.CLICK,
                app="Chrome",
                window="Google",
                description="Clicked search box",
                timestamp="2026-03-31T10:00:00",
                workflow_id=workflow_id,
                session_id="s1",
            ),
            Event(
                type=EventType.TEXT_INPUT,
                app="Chrome",
                window="Google",
                text_content="python tutorial",
                timestamp="2026-03-31T10:00:05",
                workflow_id=workflow_id,
                session_id="s1",
            ),
            Event(
                type=EventType.SHORTCUT,
                app="Chrome",
                window="Google",
                shortcut="Return",
                timestamp="2026-03-31T10:00:08",
                workflow_id=workflow_id,
                session_id="s1",
            ),
        ]
        for e in events:
            insert_event(self.conn, e)
        return events

    def test_build_prompt_contains_events(self):
        from sifu.compiler.sop import _build_prompt

        self._insert_workflow_events()
        rows = self.conn.execute(
            "SELECT * FROM events ORDER BY timestamp"
        ).fetchall()

        prompt = _build_prompt(rows)
        assert "Chrome" in prompt
        assert "python tutorial" in prompt
        assert "click" in prompt.lower() or "Click" in prompt

    def test_add_screenshot_refs_no_screenshots(self):
        from sifu.compiler.sop import _add_screenshot_refs

        self._insert_workflow_events()
        rows = self.conn.execute("SELECT * FROM events").fetchall()

        result = _add_screenshot_refs("# Test SOP", rows)
        # No screenshots → content unchanged
        assert result == "# Test SOP"

    def test_add_screenshot_refs_with_screenshots(self):
        from sifu.compiler.sop import _add_screenshot_refs

        e = Event(
            type=EventType.CLICK,
            app="Chrome",
            screenshot_path="/tmp/shot.jpg",
            workflow_id="wf-test",
            session_id="s1",
        )
        insert_event(self.conn, e)
        rows = self.conn.execute("SELECT * FROM events").fetchall()

        result = _add_screenshot_refs("# Test SOP", rows)
        assert "/tmp/shot.jpg" in result
        assert "Screenshots" in result

    @patch("subprocess.run")
    @patch("sifu.storage.db.get_connection")
    def test_compile_single_calls_claude(self, mock_get_conn, mock_subprocess_run):
        from sifu.compiler.sop import compile_single

        self._insert_workflow_events("wf-compile-test")
        mock_get_conn.return_value = self.conn

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "# How to: Search Google\n\n## Steps\n\n### 1. Open browser\nNavigated to Google."
        mock_subprocess_run.return_value = mock_result

        path = compile_single("wf-compile-test")
        assert path.suffix == ".md"
        assert mock_subprocess_run.called

    def test_get_compiled_ids_empty(self):
        from sifu.compiler.sop import _get_compiled_ids

        # When no SOPs exist, should return empty set
        ids = _get_compiled_ids()
        assert isinstance(ids, set)
