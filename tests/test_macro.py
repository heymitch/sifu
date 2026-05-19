import sqlite3
from unittest.mock import patch, MagicMock

from sifu.compiler.macro import build_macro
from sifu.events import Event, EventType
from sifu.storage.db import SCHEMA, insert_event
from sifu import library


def _rows():
    return [
        {"type": "click", "app": "Google Chrome", "position_x": 840, "position_y": 312,
         "display_id": 1, "display_bounds": "[0,0,1920,1080]",
         "window_rect": "[120,80,1280,800]", "backing_scale": 2.0,
         "url": "https://app.stripe.com/cart", "screenshot_path": "/s/4.jpg",
         "text_content": None, "shortcut": None, "window": "Cart"},
        {"type": "text_input", "app": "Google Chrome", "position_x": None, "position_y": None,
         "display_id": None, "display_bounds": None, "window_rect": None, "backing_scale": None,
         "url": "https://app.stripe.com/checkout", "screenshot_path": None,
         "text_content": "gift", "shortcut": None, "window": "Checkout"},
    ]

def test_macro_shape_and_contract():
    m = build_macro("wf-x", _rows())
    assert m["schema_version"] == 1
    assert m["workflow_id"] == "wf-x"
    s0 = m["steps"][0]
    assert s0["action"] == "click"
    assert s0["coords"] == {"x": 840, "y": 312, "rel_to": "window"}
    assert s0["frame"]["window_rect"] == [120, 80, 1280, 800]
    assert s0["frame"]["backing_scale"] == 2.0
    assert s0["url"] == "https://app.stripe.com/cart"
    assert s0["screenshot"] == "screenshots/000.jpg"
    assert s0["expected"] == {"kind": "url", "value": "https://app.stripe.com/checkout"}

def test_macro_degrades_when_frame_null():
    m = build_macro("wf-y", [{"type": "click", "app": "Notes", "position_x": 10,
        "position_y": 20, "display_id": None, "display_bounds": None,
        "window_rect": None, "backing_scale": None, "url": None,
        "screenshot_path": None, "text_content": None, "shortcut": None, "window": "Notes"}])
    s = m["steps"][0]
    assert s["coords"] == {"x": 10, "y": 20, "rel_to": "screen"}
    assert s["frame"] is None
    assert s["expected"] is None

def test_macro_empty_rows():
    m = build_macro("wf-empty", [])
    assert m == {"schema_version": 1, "workflow_id": "wf-empty", "steps": []}

def test_expected_falls_back_to_window_title_when_no_url():
    rows = [
        {"type": "click", "app": "Notes", "position_x": 5, "position_y": 6,
         "window_rect": None, "display_id": None, "display_bounds": None,
         "backing_scale": None, "url": None, "screenshot_path": None,
         "text_content": None, "shortcut": None, "window": "Note A"},
        {"type": "click", "app": "Notes", "position_x": 7, "position_y": 8,
         "window_rect": None, "display_id": None, "display_bounds": None,
         "backing_scale": None, "url": None, "screenshot_path": None,
         "text_content": None, "shortcut": None, "window": "Note B"},
    ]
    m = build_macro("wf-w", rows)
    assert m["steps"][0]["expected"] == {"kind": "window_title", "value": "Note B"}

def test_shortcut_and_app_switch_actions():
    rows = [
        {"type": "shortcut", "app": "VS Code", "position_x": None, "position_y": None,
         "window_rect": None, "display_id": None, "display_bounds": None,
         "backing_scale": None, "url": None, "screenshot_path": None,
         "text_content": None, "shortcut": "cmd+s", "window": "main.py"},
        {"type": "app_switch", "app": "Slack", "position_x": None, "position_y": None,
         "window_rect": None, "display_id": None, "display_bounds": None,
         "backing_scale": None, "url": None, "screenshot_path": None,
         "text_content": None, "shortcut": None, "window": "Slack"},
    ]
    m = build_macro("wf-k", rows)
    assert m["steps"][0]["action"] == "key"
    assert m["steps"][0]["key"] == "cmd+s"
    assert m["steps"][1]["action"] == "app_switch"

def test_malformed_window_rect_degrades_to_screen():
    rows = [{"type": "click", "app": "X", "position_x": 1, "position_y": 2,
             "window_rect": "not-json", "display_id": None, "display_bounds": None,
             "backing_scale": None, "url": None, "screenshot_path": None,
             "text_content": None, "shortcut": None, "window": "X"}]
    m = build_macro("wf-bad", rows)
    assert m["steps"][0]["frame"] is None
    assert m["steps"][0]["coords"] == {"x": 1, "y": 2, "rel_to": "screen"}


def test_compile_single_writes_library_unit(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    insert_event(conn, Event(type=EventType.CLICK, app="Google Chrome",
        position_x=10, position_y=20, url="https://x.test",
        workflow_id="wf-int-001", session_id="s1",
        timestamp="2026-05-19T10:00:00"))
    conn.commit()

    with patch("sifu.compiler.sop.get_connection", return_value=conn), \
         patch("subprocess.run") as mrun:
        mrun.return_value = MagicMock(returncode=0, stdout="# I see you do this.\n")
        from sifu.compiler.sop import compile_single
        out = compile_single("wf-int-001")

    assert out == library.unit_dir("wf-int-001")
    assert (out / "macro.json").exists()
    assert (out / "meta.json").exists()
    assert (out / "workflow.md").read_text().startswith("# I see")
    assert "I see you do this" in (out / "workflow.md").read_text()
