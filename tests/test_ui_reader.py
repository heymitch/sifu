from sifu import library
from sifu_ui import reader

def test_timeline_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    library.write_unit("wf-2026-05-19-001", "# Send an invoice\nbody",
        {"schema_version":1,"workflow_id":"wf-2026-05-19-001","steps":[{"index":0}]},
        {"id":"wf-2026-05-19-001","captured_at":"2026-05-19T10:00:00",
         "app_set":["Google Chrome"],"step_count":1}, [])
    rows = reader.timeline()
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == "wf-2026-05-19-001"
    assert r["title"] == "Send an invoice"
    assert r["captured_at"] == "2026-05-19T10:00:00"
    assert r["step_count"] == 1
