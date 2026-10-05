"""After `sifu compile`, macOS opens each unit and posts a notification.
Other platforms skip both instead of crashing."""

import json
import subprocess
import sys
from unittest.mock import patch

import pytest

from sifu import config, library
from sifu.compiler.sop import compile_workflows
from sifu.events import Event, EventType
from sifu.storage import db


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "capture.db")
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    conn = db.init_db()
    for i, (typ, kw) in enumerate([
        (EventType.APP_SWITCH, {"app": "Chrome", "description": "Switched to Chrome"}),
        (EventType.CLICK, {"app": "Chrome", "description": "Clicked New", "position_x": 1, "position_y": 2}),
        (EventType.TEXT_INPUT, {"app": "Chrome", "text_content": "hello"}),
        (EventType.CLICK, {"app": "Chrome", "description": "Clicked Save", "position_x": 3, "position_y": 4}),
    ]):
        db.insert_event(conn, Event(type=typ, timestamp=f"2026-10-03T10:00:0{i}", session_id="s1", **kw))
    conn.close()
    return tmp_path


def _compile(platform, monkeypatch):
    monkeypatch.setattr(sys, "platform", platform)
    with patch.object(subprocess, "Popen") as popen:
        compile_workflows(today=True)
    return [c.args[0] for c in popen.call_args_list]


def test_macos_opens_the_unit_and_notifies(seeded, monkeypatch):
    calls = _compile("darwin", monkeypatch)
    unit = library.LIBRARY_DIR / "wf-2026-10-03-001"
    assert calls == [
        ["open", str(unit)],
        ["osascript", "-e",
         f'display notification "1 workflow compiled → {library.LIBRARY_DIR}" with title "Sifu"'],
    ]


def test_macos_opens_with_the_configured_editor(seeded, monkeypatch):
    config.CONFIG_PATH.write_text(json.dumps({"editor": "Sublime Text"}))
    calls = _compile("darwin", monkeypatch)
    assert calls[0] == ["open", "-a", "Sublime Text", str(library.LIBRARY_DIR / "wf-2026-10-03-001")]


def test_linux_compiles_without_desktop_calls(seeded, monkeypatch):
    assert _compile("linux", monkeypatch) == []
    assert (library.LIBRARY_DIR / "wf-2026-10-03-001" / "workflow.md").exists()


def test_screenshots_keep_their_step_number_when_some_steps_have_none(tmp_path, monkeypatch):
    from sifu.compiler.sop import compile_single

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "capture.db")
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    shot = tmp_path / "shot.jpg"
    shot.write_bytes(b"step-1-pixels")
    conn = db.init_db()
    db.insert_event(conn, Event(type=EventType.TEXT_INPUT, timestamp="2026-10-03T10:00:00",
                                app="Chrome", text_content="hi", workflow_id="wf-s"))
    db.insert_event(conn, Event(type=EventType.CLICK, timestamp="2026-10-03T10:00:01",
                                app="Chrome", screenshot_path=str(shot), workflow_id="wf-s"))
    conn.close()

    unit = compile_single("wf-s")

    steps = json.loads((unit / "macro.json").read_text())["steps"]
    assert [s["screenshot"] for s in steps] == [None, "screenshots/001.jpg"]
    assert (unit / "screenshots" / "001.jpg").read_bytes() == b"step-1-pixels"
    assert not (unit / "screenshots" / "000.jpg").exists()
