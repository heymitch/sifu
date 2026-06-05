"""Tests for `sifu open` — open the dashboard to the list or the latest workflow."""

from sifu.open_cmd import open_dashboard


def test_open_dashboard_without_last_opens_index():
    """Manual open (no --last) lands on the list view at '/'."""
    opened = []
    open_dashboard(
        last=False,
        is_server_up=lambda port: True,
        start_server=lambda port: None,
        open_url=opened.append,
    )
    assert opened == ["http://localhost:8765/"]


def test_open_dashboard_with_last_opens_the_latest_workflow():
    """Auto-open (--last) lands on the single workflow you just compiled."""
    opened = []
    open_dashboard(
        last=True,
        latest_unit=lambda: "wf-abc123",
        is_server_up=lambda port: True,
        start_server=lambda port: None,
        open_url=opened.append,
    )
    assert opened == ["http://localhost:8765/workflow/wf-abc123"]


def test_open_dashboard_starts_server_when_down_then_opens():
    """If the UI server isn't up, start it before opening the browser."""
    events = []
    open_dashboard(
        last=False,
        is_server_up=lambda port: False,
        start_server=lambda port: events.append(("start", port)),
        open_url=lambda url: events.append(("open", url)),
    )
    assert events == [("start", 8765), ("open", "http://localhost:8765/")]


def test_open_dashboard_does_not_start_server_when_already_up():
    """Don't double-spawn: a live server means no start_server call."""
    events = []
    open_dashboard(
        last=False,
        is_server_up=lambda port: True,
        start_server=lambda port: events.append("start"),
        open_url=lambda url: events.append("open"),
    )
    assert events == ["open"]


def test_open_dashboard_last_with_no_workflows_opens_nothing():
    """--last with an empty library: don't open a broken /workflow/None, and
    don't bother spinning up the server for nothing."""
    events = []
    open_dashboard(
        last=True,
        latest_unit=lambda: None,
        is_server_up=lambda port: True,
        start_server=lambda port: events.append("start"),
        open_url=lambda url: events.append(("open", url)),
    )
    assert events == []
