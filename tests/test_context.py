from sifu import library, context_cmd


def _seed(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    library.write_unit(
        "wf-deploy-001", "# Deploy the site\nPush to Vercel.",
        {"schema_version": 1, "workflow_id": "wf-deploy-001", "steps": []},
        {"id": "wf-deploy-001", "app_set": ["Terminal"], "step_count": 0,
         "captured_at": "2026-05-28T10:00:00", "duration_seconds": 42},
        [],
    )
    library.write_unit(
        "wf-invoice-001", "# Send an invoice\nOpen Stripe.",
        {"schema_version": 1, "workflow_id": "wf-invoice-001", "steps": []},
        {"id": "wf-invoice-001", "app_set": ["Google Chrome"]},
        [],
    )
    # A unit whose distinguishing text lives ONLY in the macro's typed steps,
    # not the workflow.md prose — exercises the macro-text matcher.
    library.write_unit(
        "wf-email-001", "# Compose a message\nWrite the body.",
        {"schema_version": 1, "workflow_id": "wf-email-001",
         "steps": [{"action": "type", "text": "quarterly newsletter sendout"}]},
        {"id": "wf-email-001", "app_set": ["Kit"]},
        [],
    )


def test_match_by_title(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    assert context_cmd.best_match("deploy") == "wf-deploy-001"
    assert context_cmd.best_match("invoice stripe") == "wf-invoice-001"
    assert context_cmd.best_match("nonexistent zzz") is None


def test_match_by_macro_typed_text(tmp_path, monkeypatch):
    """A query matching the macro's typed text (not the prose) still matches."""
    _seed(tmp_path, monkeypatch)
    assert context_cmd.best_match("newsletter sendout") == "wf-email-001"


def test_context_output_is_skill_building_briefing(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    out = context_cmd.render_context("deploy")
    # Masthead + the recorded flow + evidence pointers
    assert "SIFU RECORDING" in out
    assert "wf-deploy-001" in out
    assert "# Deploy the site" in out
    assert str(library.unit_dir("wf-deploy-001") / "macro.json") in out
    # The knowledge payload: build an artifact, don't just replay
    assert "ANALYZE" in out
    assert "SKILL" in out and "ORCHESTRATOR" in out
    # Tool ladder + accountability model + cost framing
    assert "most efficient first" in out.lower()
    assert "accountable execution" in out.lower()
    assert "notify" in out
    assert "subscription" in out.lower()
    # NOT headlined as a blind NavMacro replay anymore
    assert "drive the macro at the path above with the" not in out


def test_render_context_returns_none_on_no_match(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    assert context_cmd.render_context("nothing-matches-zzz-xyz") is None


def test_output_leads_with_skill_directive(tmp_path, monkeypatch):
    """Pasted blob should read as a command (init-style), not a passive dump."""
    _seed(tmp_path, monkeypatch)
    out = context_cmd.render_context("deploy")
    assert "agent skill" in out.lower()
    # directive sits at the very top, before the masthead
    assert out.index("agent skill") < out.index("SIFU RECORDING")


def test_render_latest_picks_newest_unit(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    # wf-email-001 carries no captured_at; give the others none too, then add a
    # newest one to assert selection by captured_at.
    library.write_unit(
        "wf-latest-001", "# The newest thing\nDo it.",
        {"schema_version": 1, "workflow_id": "wf-latest-001", "steps": []},
        {"id": "wf-latest-001", "app_set": ["Kit"], "captured_at": "2099-01-01T00:00:00"},
        [],
    )
    out = context_cmd.render_latest()
    assert out is not None
    assert "wf-latest-001" in out
    assert "# The newest thing" in out


def test_render_latest_none_when_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    assert context_cmd.render_latest() is None


def test_bootstrap_creates_library(tmp_path, monkeypatch):
    from sifu.install import bootstrap
    monkeypatch.setattr(bootstrap.library, "LIBRARY_DIR", tmp_path / "library")
    result = bootstrap.run()
    assert (tmp_path / "library").is_dir()
    assert result["library"] == str(tmp_path / "library")
