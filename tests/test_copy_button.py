"""Click-to-copy: the dashboard serves the agent-ready payload per workflow."""

from fastapi.testclient import TestClient

from sifu import library
from sifu.compiler.macro import build_macro
from sifu.compiler.meta import build_meta
from sifu_ui.app import app


def _seed(monkeypatch, tmp_path, wid="wf-c"):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    rows = [{"app": "Chrome", "type": "click", "timestamp": "2026-06-05T10:00:00"}]
    library.write_unit(wid, workflow_md=f"# Workflow: Chrome\n\n## Step 1 — Chrome\nClicked\n",
                       macro=build_macro(wid, rows), meta=build_meta(wid, rows), screenshots=[])


def test_payload_route_returns_the_agent_briefing(tmp_path, monkeypatch):
    _seed(monkeypatch, tmp_path)
    client = TestClient(app)

    r = client.get("/workflow/wf-c/payload")

    assert r.status_code == 200
    assert "What to do with this" in r.text  # the full copy-to-agent payload


def test_payload_route_404_for_missing_workflow(tmp_path, monkeypatch):
    _seed(monkeypatch, tmp_path)
    client = TestClient(app)

    assert client.get("/workflow/nope/payload").status_code == 404
