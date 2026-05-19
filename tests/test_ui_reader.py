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


def test_app_serves_timeline_with_design_system(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    library.write_unit("wf-2026-05-19-001", "# Send an invoice\nbody",
        {"schema_version":1,"workflow_id":"wf-2026-05-19-001","steps":[]},
        {"id":"wf-2026-05-19-001","captured_at":"2026-05-19T10:00:00",
         "app_set":["Chrome"],"step_count":0}, [])
    from fastapi.testclient import TestClient
    from sifu_ui.app import app
    c = TestClient(app)
    html = c.get("/").text
    assert "Send an invoice" in html
    assert "sifu-design.css" in html
    assert "WORKFLOW ·" in html
    for banned in ("box-shadow", "linear-gradient", "backdrop-filter", "😀"):
        assert banned not in html
    assert c.get("/workflow/wf-2026-05-19-001").status_code == 200
