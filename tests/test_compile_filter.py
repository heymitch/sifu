"""`--today` should mean 'the latest day you actually recorded', not the
wall-clock date — otherwise a session captured before midnight silently fails
to compile the next morning."""

from sifu.compiler.sop import _filter_to_latest_day


def test_keeps_only_most_recent_day():
    segs = [
        {"workflow_id": "a", "start_time": "2026-05-28T10:00:00"},
        {"workflow_id": "b", "start_time": "2026-05-28T11:00:00"},
        {"workflow_id": "c", "start_time": "2026-05-27T09:00:00"},
    ]
    out = _filter_to_latest_day(segs)
    assert {s["workflow_id"] for s in out} == {"a", "b"}


def test_robust_to_clock_rollover():
    # Latest captured day is in the past relative to 'now' — still compiles.
    segs = [{"workflow_id": "x", "start_time": "2020-01-01T10:00:00"}]
    assert [s["workflow_id"] for s in _filter_to_latest_day(segs)] == ["x"]


def test_empty():
    assert _filter_to_latest_day([]) == []
