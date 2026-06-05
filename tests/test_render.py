"""Tests for deterministic workflow-markdown rendering (no LLM)."""

from sifu.compiler.render import render_workflow_md


def _row(**kw):
    base = {"app": "Chrome", "type": "click", "timestamp": "2026-06-05T14:23:01"}
    base.update(kw)
    return base


def test_renders_one_step_per_event():
    rows = [
        _row(timestamp="2026-06-05T14:23:01"),
        _row(timestamp="2026-06-05T14:23:05"),
        _row(timestamp="2026-06-05T14:23:09"),
    ]
    md = render_workflow_md("wf-1", rows)
    assert md.count("\n## Step ") == 3


def test_step_describes_action_and_app():
    rows = [
        _row(app="Chrome", type="click"),
        _row(app="Slack", type="text_input", text_content="hello team"),
        _row(app="Cursor", type="app_switch"),
        _row(app="Chrome", type="shortcut", shortcut="cmd+t"),
    ]
    md = render_workflow_md("wf-1", rows)
    assert "Typed: hello team" in md
    assert "Switched to Cursor" in md
    assert "Pressed cmd+t" in md
    assert "Slack" in md  # app label present


def test_step_with_screenshot_embeds_the_image():
    rows = [_row(screenshot_path="/abs/000.jpg"), _row()]  # only the first has a shot
    md = render_workflow_md("wf-1", rows)
    assert "![step 1](screenshots/000.jpg)" in md
    assert "screenshots/001.jpg" not in md  # step 2 has none


def test_has_title_and_header_summary():
    rows = [
        _row(app="Chrome", timestamp="2026-06-05T14:23:01"),
        _row(app="Slack", timestamp="2026-06-05T14:25:31"),
    ]
    md = render_workflow_md("wf-1", rows)
    first = next(l for l in md.splitlines() if l.strip())
    assert first.startswith("# ")          # reader.timeline uses this as the title
    assert "2 steps" in md
    assert "Chrome" in md and "Slack" in md


def test_step_shows_pretty_timestamp_not_raw_iso():
    rows = [_row(timestamp="2026-06-05T14:23:01")]
    md = render_workflow_md("wf-1", rows)
    assert "2026-06-05T14:23:01" not in md  # raw ISO never leaks through
    assert "2:23" in md                     # rendered as a friendly clock time
