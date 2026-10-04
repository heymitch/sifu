"""docs/capture-contract.md, the Python schema, the Event model and the Swift
writer must describe the same events table."""

import dataclasses
import re
import sqlite3
from pathlib import Path

from sifu.events import Event, EventType
from sifu.storage.db import SCHEMA

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "capture-contract.md"
SWIFT_STORE = ROOT / "extras" / "SifuBar" / "SifuBar" / "Storage" / "EventStore.swift"

EVENT_COLUMNS = [
    "id", "timestamp", "type", "app", "window", "description", "element",
    "position_x", "position_y", "text_content", "shortcut", "screenshot_path",
    "display_id", "display_bounds", "window_rect", "backing_scale", "url",
    "session_id", "workflow_id",
]


def _columns(schema_sql: str, table: str) -> list[str]:
    conn = sqlite3.connect(":memory:")
    conn.executescript(schema_sql)
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _doc_sql() -> str:
    return re.search(r"```sql\n(.*?)```", DOC.read_text(), re.S).group(1)


def _swift_sql() -> str:
    return re.search(r'let sql = """\n(.*?)"""', SWIFT_STORE.read_text(), re.S).group(1)


def test_python_schema_has_the_contract_columns():
    assert _columns(SCHEMA, "events") == EVENT_COLUMNS
    assert _columns(SCHEMA, "sessions") == ["id", "start_time", "end_time", "app_summary"]


def test_doc_schema_is_the_python_schema():
    assert " ".join(_doc_sql().split()) == " ".join(SCHEMA.split())


def test_swift_writer_creates_the_same_columns():
    assert sorted(_columns(_swift_sql(), "events")) == sorted(EVENT_COLUMNS)
    assert _columns(_swift_sql(), "sessions") == ["id", "start_time", "end_time", "app_summary"]


def test_event_model_fields_are_the_columns():
    assert sorted(f.name for f in dataclasses.fields(Event)) == sorted(EVENT_COLUMNS)


def test_doc_lists_every_event_type():
    doc = DOC.read_text()
    for t in EventType:
        assert f"`{t.value}`" in doc, t.value


def test_click_coords_become_window_relative_in_the_macro():
    from sifu.compiler.macro import build_macro

    # Capture stores the click and the window origin in the same global space.
    click = {"type": "click", "app": "Chrome", "position_x": 840, "position_y": 312,
             "window_rect": "[120, 80, 1280, 800]", "display_id": 1,
             "display_bounds": "[0, 0, 1920, 1080]", "backing_scale": 2.0}
    assert build_macro("wf", [click])["steps"][0]["coords"] == {"x": 720, "y": 232, "rel_to": "window"}

    no_window = {**click, "window_rect": None}
    assert build_macro("wf", [no_window])["steps"][0]["coords"] == {"x": 840, "y": 312, "rel_to": "screen"}
