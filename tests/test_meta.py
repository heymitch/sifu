from sifu.compiler.meta import build_meta

def test_meta():
    rows = [
        {"type":"click","app":"Google Chrome","timestamp":"2026-05-19T10:00:00","session_id":"s1"},
        {"type":"type","app":"Slack","timestamp":"2026-05-19T10:02:30","session_id":"s1"},
    ]
    m = build_meta("wf-2026-05-19-001", rows)
    assert m["id"] == "wf-2026-05-19-001"
    assert m["step_count"] == 2
    assert sorted(m["app_set"]) == ["Google Chrome", "Slack"]
    assert m["captured_at"] == "2026-05-19T10:00:00"
    assert m["source_session"] == "s1"
    assert m["duration_seconds"] == 150
