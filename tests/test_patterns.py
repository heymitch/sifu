"""Tests for Sifu pattern engine (Layer 1)."""

import json
from datetime import datetime, timedelta

import pytest

from sifu.patterns.engine import segment_workflows


def _make_event(type, app, timestamp_str, text_content=None, shortcut=None, id=None):
    """Create a dict that looks like a sqlite3.Row for testing."""
    return {
        "id": id or 1,
        "type": type,
        "app": app,
        "timestamp": timestamp_str,
        "text_content": text_content,
        "shortcut": shortcut,
        "window": None,
        "description": None,
        "element": None,
        "position_x": None,
        "position_y": None,
        "screenshot_path": None,
        "session_id": "test",
        "workflow_id": None,
    }


class TestSegmentation:
    def test_empty_events(self):
        segments = segment_workflows([])
        assert segments == []

    def test_single_event(self):
        events = [_make_event("click", "Chrome", "2026-03-31T10:00:00", id=1)]
        segments = segment_workflows(events)
        assert len(segments) == 1
        assert segments[0]["event_count"] == 1

    def test_same_app_continuous(self):
        """Events in the same app with small gaps stay in one segment."""
        base = datetime(2026, 3, 31, 10, 0, 0)
        events = [
            _make_event("click", "Chrome", (base + timedelta(seconds=i * 5)).isoformat(), id=i + 1)
            for i in range(5)
        ]
        segments = segment_workflows(events)
        assert len(segments) == 1
        assert segments[0]["event_count"] == 5

    def test_app_switch_short_gap_no_split(self):
        """App switch with <30s gap does NOT split."""
        events = [
            _make_event("click", "Chrome", "2026-03-31T10:00:00", id=1),
            _make_event("click", "Ghostty", "2026-03-31T10:00:10", id=2),
        ]
        segments = segment_workflows(events)
        assert len(segments) == 1

    def test_app_switch_long_gap_splits(self):
        """App switch with >30s gap creates a new segment."""
        events = [
            _make_event("click", "Chrome", "2026-03-31T10:00:00", id=1),
            _make_event("click", "Ghostty", "2026-03-31T10:01:00", id=2),
        ]
        segments = segment_workflows(events)
        assert len(segments) == 2

    def test_idle_boundary(self):
        """5+ minute gap creates a session boundary (new segment)."""
        events = [
            _make_event("click", "Chrome", "2026-03-31T10:00:00", id=1),
            _make_event("click", "Chrome", "2026-03-31T10:06:00", id=2),
        ]
        segments = segment_workflows(events)
        assert len(segments) == 2

    def test_terminal_commands_cluster(self):
        """Sequential terminal commands in the same app stay together."""
        base = datetime(2026, 3, 31, 10, 0, 0)
        events = [
            _make_event("command", "Ghostty", (base + timedelta(seconds=i * 3)).isoformat(),
                        text_content=f"cmd{i}", id=i + 1)
            for i in range(4)
        ]
        segments = segment_workflows(events)
        assert len(segments) == 1
        assert segments[0]["event_count"] == 4

    def test_segment_has_required_fields(self):
        events = [_make_event("click", "Chrome", "2026-03-31T10:00:00", id=1)]
        segments = segment_workflows(events)
        seg = segments[0]
        assert "workflow_id" in seg
        assert "title" in seg
        assert "app" in seg
        assert "event_ids" in seg
        assert "event_count" in seg
        assert "start_time" in seg
        assert "end_time" in seg
        assert "pattern_count" in seg
        assert "automation_candidate" in seg

    def test_workflow_id_format(self):
        events = [_make_event("click", "Chrome", "2026-03-31T10:00:00", id=1)]
        segments = segment_workflows(events)
        assert segments[0]["workflow_id"].startswith("wf-")

    def test_title_contains_app(self):
        events = [_make_event("click", "Chrome", "2026-03-31T10:00:00", id=1)]
        segments = segment_workflows(events)
        assert "Chrome" in segments[0]["title"]

    def test_multiple_segments(self):
        """Complex scenario with multiple segment boundaries."""
        events = [
            # Segment 1: Chrome activity
            _make_event("click", "Chrome", "2026-03-31T10:00:00", id=1),
            _make_event("click", "Chrome", "2026-03-31T10:00:05", id=2),
            # 2 minute gap + app switch → new segment
            _make_event("command", "Ghostty", "2026-03-31T10:02:10", text_content="git status", id=3),
            _make_event("command", "Ghostty", "2026-03-31T10:02:15", text_content="git add .", id=4),
            # 6 minute idle gap → session boundary
            _make_event("click", "Chrome", "2026-03-31T10:08:20", id=5),
        ]
        segments = segment_workflows(events)
        assert len(segments) == 3
