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

    # NOTE: tests for _build_prompt / _add_screenshot_refs were removed — SOP
    # generation now delegates to the Claude CLI (compile_single), so those
    # internal helpers no longer exist.

    def test_compile_single_renders_deterministically(self, tmp_path, monkeypatch):
        from sifu import library
        monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")

        from sifu.compiler.sop import compile_single

        self._insert_workflow_events("wf-compile-test")

        with patch("sifu.compiler.sop.get_connection", return_value=self.conn), \
             patch("subprocess.run") as mock_subprocess_run:
            out = compile_single("wf-compile-test")

        assert out == library.unit_dir("wf-compile-test")
        assert (out / "macro.json").exists()
        assert (out / "meta.json").exists()
        assert (out / "workflow.md").exists()
        # Deterministic compile: no LLM / subprocess call, structured steps emitted.
        assert not mock_subprocess_run.called
        assert "## Step " in (out / "workflow.md").read_text()

    def test_get_compiled_ids_empty(self):
        from sifu.compiler.sop import _get_compiled_ids

        # When no SOPs exist, should return empty set
        ids = _get_compiled_ids()
        assert isinstance(ids, set)
