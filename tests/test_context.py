from sifu import library, context_cmd

def _seed(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    library.write_unit("wf-deploy-001", "# Deploy the site\nPush to Vercel.",
        {"schema_version":1,"workflow_id":"wf-deploy-001","steps":[]},
        {"id":"wf-deploy-001","app_set":["Terminal"]}, [])
    library.write_unit("wf-invoice-001", "# Send an invoice\nOpen Stripe.",
        {"schema_version":1,"workflow_id":"wf-invoice-001","steps":[]},
        {"id":"wf-invoice-001","app_set":["Google Chrome"]}, [])

def test_match_by_title(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    assert context_cmd.best_match("deploy") == "wf-deploy-001"
    assert context_cmd.best_match("invoice stripe") == "wf-invoice-001"
    assert context_cmd.best_match("nonexistent zzz") is None

def test_context_output_has_pointer_and_instruction(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    out = context_cmd.render_context("deploy")
    assert "# Deploy the site" in out
    assert str(library.unit_dir("wf-deploy-001") / "macro.json") in out
    assert "NavMacro" in out and "vision" in out.lower()
