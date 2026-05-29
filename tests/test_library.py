"""Tests for the canonical workflow library + schema migration."""
import sqlite3
from pathlib import Path
from sifu.storage.db import SCHEMA, migrate_db
from sifu.events import Event, EventType
from sifu import library

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
    assert d["display_bounds"] == "[0,0,1920,1080]"
    assert e2.backing_scale == 2.0
    assert e2.window_rect == "[120,80,1280,800]"


def test_unit_dir_and_write(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    u = library.unit_dir("wf-2026-05-19-001")
    assert u == tmp_path / "library" / "wf-2026-05-19-001"
    library.write_unit(
        "wf-2026-05-19-001",
        workflow_md="# I see you do this.\n",
        macro={"schema_version": 1, "workflow_id": "wf-2026-05-19-001", "steps": []},
        meta={"id": "wf-2026-05-19-001", "step_count": 0},
        screenshots=[],
    )
    assert (u / "workflow.md").read_text().startswith("# I see")
    assert '"schema_version": 1' in (u / "macro.json").read_text()
    assert (u / "meta.json").exists()

def test_list_units(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    library.write_unit("wf-a", "# a", {"schema_version":1,"workflow_id":"wf-a","steps":[]}, {"id":"wf-a"}, [])
    library.write_unit("wf-b", "# b", {"schema_version":1,"workflow_id":"wf-b","steps":[]}, {"id":"wf-b"}, [])
    ids = sorted(library.list_units())
    assert ids == ["wf-a", "wf-b"]

def test_write_unit_overwrite_clears_stale_screenshots(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    s1 = tmp_path / "a.jpg"; s1.write_bytes(b"a")
    s2 = tmp_path / "b.jpg"; s2.write_bytes(b"b")
    library.write_unit("wf-ov", "# v1", {"schema_version":1,"workflow_id":"wf-ov","steps":[]}, {"id":"wf-ov"}, [s1, s2])
    shots = library.unit_dir("wf-ov") / "screenshots"
    assert sorted(p.name for p in shots.iterdir()) == ["000.jpg", "001.jpg"]
    # overwrite with ONE screenshot — stale 001.jpg must be gone
    library.write_unit("wf-ov", "# v2", {"schema_version":1,"workflow_id":"wf-ov","steps":[]}, {"id":"wf-ov"}, [s1])
    assert sorted(p.name for p in shots.iterdir()) == ["000.jpg"]


def _make_unit(session_id: str, workflow_id: str):
    """Create a minimal on-disk library unit for `workflow_id`."""
    import json
    d = library.unit_dir(workflow_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "macro.json").write_text(json.dumps({"schema_version": 1, "steps": []}), encoding="utf-8")
    (d / "meta.json").write_text(
        json.dumps({"id": workflow_id, "source_session": session_id}), encoding="utf-8"
    )
    return d


class TestUnitsForSession:
    def test_filters_by_source_session(self, tmp_path, monkeypatch):
        monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
        _make_unit("session-A", "wf-2026-05-28-001")
        _make_unit("session-A", "wf-2026-05-28-002")
        _make_unit("session-B", "wf-2026-05-28-003")
        ids = library.units_for_session("session-A")
        assert set(ids) == {"wf-2026-05-28-001", "wf-2026-05-28-002"}

    def test_empty_when_no_match(self, tmp_path, monkeypatch):
        monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
        _make_unit("session-A", "wf-2026-05-28-001")
        assert library.units_for_session("session-Z") == []


class TestRemoveUnit:
    def test_removes_existing_returns_true(self, tmp_path, monkeypatch):
        monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
        _make_unit("session-A", "wf-2026-05-28-001")
        assert library.remove_unit("wf-2026-05-28-001") is True
        assert "wf-2026-05-28-001" not in library.list_units()

    def test_missing_returns_false(self, tmp_path, monkeypatch):
        monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
        assert library.remove_unit("wf-does-not-exist") is False
