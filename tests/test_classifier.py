"""Tests for the two-phase classifier engine."""

import pytest

from sifu.classifier.discovery import Capability
from sifu.classifier.classifier import (
    BROWSER_APPS,
    TERMINAL_APPS,
    WAIT_FOR_THRESHOLD,
    WAIT_FOR_MAX,
    _match_capability,
    _time_gap,
    _detect_eliminate,
    _detect_wait_for,
    classify_step,
    classify_workflow_steps,
)


# ---------------------------------------------------------------------------
# Event factory
# ---------------------------------------------------------------------------

def _make_event(
    type,
    app,
    timestamp,
    text_content=None,
    shortcut=None,
    window=None,
    id=1,
):
    return {
        "id": id,
        "type": type,
        "app": app,
        "timestamp": timestamp,
        "text_content": text_content,
        "shortcut": shortcut,
        "window": window or "",
        "description": None,
        "element": None,
        "position_x": None,
        "position_y": None,
        "screenshot_path": None,
        "session_id": "test",
        "workflow_id": None,
    }


# ---------------------------------------------------------------------------
# Capability fixtures
# ---------------------------------------------------------------------------

def _make_cap(name, cap_type, matches, actions=None):
    return Capability(
        name=name,
        type=cap_type,
        description=f"{name} capability",
        matches=matches,
        actions=actions or [],
    )


# ---------------------------------------------------------------------------
# TestCapabilityMatching
# ---------------------------------------------------------------------------

class TestCapabilityMatching:
    def test_app_exact_match(self):
        cap = _make_cap("myapp", "cli", [{"app": "MyApp"}])
        event = _make_event("click", "MyApp", "2024-01-01T10:00:00")
        assert _match_capability(event, cap) is True

    def test_app_no_match_different_name(self):
        cap = _make_cap("myapp", "cli", [{"app": "MyApp"}])
        event = _make_event("click", "OtherApp", "2024-01-01T10:00:00")
        assert _match_capability(event, cap) is False

    def test_command_contains_match(self):
        cap = _make_cap("git", "cli", [{"command_contains": "git"}])
        event = _make_event("command", "Ghostty", "2024-01-01T10:00:00", text_content="git commit -m 'fix'")
        assert _match_capability(event, cap) is True

    def test_command_contains_case_insensitive(self):
        cap = _make_cap("git", "cli", [{"command_contains": "Git"}])
        event = _make_event("command", "Ghostty", "2024-01-01T10:00:00", text_content="git status")
        assert _match_capability(event, cap) is True

    def test_command_contains_no_match(self):
        cap = _make_cap("git", "cli", [{"command_contains": "git"}])
        event = _make_event("command", "Ghostty", "2024-01-01T10:00:00", text_content="npm install")
        assert _match_capability(event, cap) is False

    def test_url_contains_match(self):
        cap = _make_cap("notion", "mcp", [{"url_contains": "notion.so"}])
        event = _make_event("click", "Chrome", "2024-01-01T10:00:00", window="My Page - notion.so")
        assert _match_capability(event, cap) is True

    def test_mcp_server_match(self):
        cap = _make_cap("framer", "mcp", [{"mcp_server": "framer"}])
        event = _make_event("click", "Framer App", "2024-01-01T10:00:00")
        assert _match_capability(event, cap) is True

    def test_no_match_empty_patterns(self):
        cap = _make_cap("empty", "cli", [])
        event = _make_event("command", "Ghostty", "2024-01-01T10:00:00", text_content="anything")
        assert _match_capability(event, cap) is False

    def test_multiple_patterns_first_matches(self):
        cap = _make_cap("multi", "cli", [
            {"command_contains": "docker"},
            {"app": "Docker"},
        ])
        event = _make_event("command", "Ghostty", "2024-01-01T10:00:00", text_content="docker build .")
        assert _match_capability(event, cap) is True

    def test_multiple_patterns_second_matches(self):
        cap = _make_cap("multi", "cli", [
            {"command_contains": "docker"},
            {"app": "Docker"},
        ])
        event = _make_event("click", "Docker", "2024-01-01T10:00:00")
        assert _match_capability(event, cap) is True


# ---------------------------------------------------------------------------
# TestEliminateDetection
# ---------------------------------------------------------------------------

class TestEliminateDetection:
    def test_app_switch_eliminated(self):
        event = _make_event("app_switch", "Chrome", "2024-01-01T10:00:00")
        reason = _detect_eliminate(event, None, None)
        assert reason is not None
        assert "app_switch" in reason

    def test_window_switch_eliminated(self):
        event = _make_event("window_switch", "Chrome", "2024-01-01T10:00:00")
        reason = _detect_eliminate(event, None, None)
        assert reason is not None
        assert "window_switch" in reason

    def test_command_not_eliminated(self):
        event = _make_event("command", "Ghostty", "2024-01-01T10:00:00", text_content="git status")
        reason = _detect_eliminate(event, None, None)
        assert reason is None

    def test_click_not_eliminated(self):
        event = _make_event("click", "Chrome", "2024-01-01T10:00:00")
        reason = _detect_eliminate(event, None, None)
        assert reason is None

    def test_shortcut_not_eliminated(self):
        event = _make_event("shortcut", "Chrome", "2024-01-01T10:00:00", shortcut="cmd+c")
        reason = _detect_eliminate(event, None, None)
        assert reason is None


# ---------------------------------------------------------------------------
# TestWaitForDetection
# ---------------------------------------------------------------------------

class TestWaitForDetection:
    def _ts(self, seconds_offset: float) -> str:
        """Generate ISO timestamp with given offset from base."""
        from datetime import datetime, timezone
        base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        from datetime import timedelta
        t = base + timedelta(seconds=seconds_offset)
        return t.isoformat().replace("+00:00", "")

    def test_same_app_gap_within_range_returns_condition(self):
        prev = _make_event("click", "Chrome", self._ts(0), id=1)
        curr = _make_event("click", "Chrome", self._ts(5.0), id=2)
        result = _detect_wait_for(curr, prev)
        assert result is not None
        assert result["app"] == "Chrome"
        assert result["estimated_wait"] == 5.0

    def test_browser_app_gets_page_loaded_type(self):
        prev = _make_event("click", "Chrome", self._ts(0), id=1)
        curr = _make_event("click", "Chrome", self._ts(3.0), id=2)
        result = _detect_wait_for(curr, prev)
        assert result is not None
        assert result["type"] == "page_loaded"

    def test_terminal_app_gets_command_complete_type(self):
        prev = _make_event("command", "Ghostty", self._ts(0), id=1)
        curr = _make_event("command", "Ghostty", self._ts(4.0), id=2)
        result = _detect_wait_for(curr, prev)
        assert result is not None
        assert result["type"] == "command_complete"

    def test_other_app_gets_app_ready_type(self):
        prev = _make_event("click", "Figma", self._ts(0), id=1)
        curr = _make_event("click", "Figma", self._ts(5.0), id=2)
        result = _detect_wait_for(curr, prev)
        assert result is not None
        assert result["type"] == "app_ready"

    def test_short_gap_below_threshold_returns_none(self):
        prev = _make_event("click", "Chrome", self._ts(0), id=1)
        curr = _make_event("click", "Chrome", self._ts(1.0), id=2)
        result = _detect_wait_for(curr, prev)
        assert result is None

    def test_gap_above_max_returns_none(self):
        prev = _make_event("click", "Chrome", self._ts(0), id=1)
        curr = _make_event("click", "Chrome", self._ts(65.0), id=2)
        result = _detect_wait_for(curr, prev)
        assert result is None

    def test_different_app_returns_none(self):
        prev = _make_event("click", "Chrome", self._ts(0), id=1)
        curr = _make_event("click", "Ghostty", self._ts(5.0), id=2)
        result = _detect_wait_for(curr, prev)
        assert result is None

    def test_no_prev_event_returns_none(self):
        curr = _make_event("click", "Chrome", self._ts(5.0), id=2)
        result = _detect_wait_for(curr, None)
        assert result is None

    def test_exact_threshold_gap_returns_condition(self):
        """Gap exactly at WAIT_FOR_THRESHOLD should be treated as wait."""
        prev = _make_event("click", "Chrome", self._ts(0), id=1)
        curr = _make_event("click", "Chrome", self._ts(WAIT_FOR_THRESHOLD), id=2)
        result = _detect_wait_for(curr, prev)
        assert result is not None

    def test_just_below_max_returns_condition(self):
        prev = _make_event("click", "Chrome", self._ts(0), id=1)
        curr = _make_event("click", "Chrome", self._ts(WAIT_FOR_MAX - 0.1), id=2)
        result = _detect_wait_for(curr, prev)
        assert result is not None


# ---------------------------------------------------------------------------
# TestClassifyStep
# ---------------------------------------------------------------------------

class TestClassifyStep:
    def _ts(self, offset: float = 0) -> str:
        from datetime import datetime, timezone, timedelta
        base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        return (base + timedelta(seconds=offset)).isoformat().replace("+00:00", "")

    def test_command_with_capability_match_gets_cli(self):
        git_cap = _make_cap("git", "cli", [{"command_contains": "git"}])
        event = _make_event("command", "Ghostty", self._ts(), text_content="git status")
        step = classify_step(event, [git_cap], step_id=1)
        assert step.method == "cli"
        assert step.capability == "git"
        assert step.confidence == 0.85

    def test_app_switch_gets_eliminated(self):
        event = _make_event("app_switch", "Chrome", self._ts())
        step = classify_step(event, [], step_id=1)
        assert step.method == "eliminate"
        assert step.confidence == 0.90

    def test_window_switch_gets_eliminated(self):
        event = _make_event("window_switch", "Arc", self._ts())
        step = classify_step(event, [], step_id=1)
        assert step.method == "eliminate"

    def test_unknown_event_gets_manual(self):
        event = _make_event("unknown_action", "SomeApp", self._ts())
        step = classify_step(event, [], step_id=1)
        assert step.method == "manual"
        assert step.confidence == 0.30

    def test_browser_click_gets_browser_method(self):
        event = _make_event("click", "Chrome", self._ts())
        step = classify_step(event, [], step_id=1)
        assert step.method == "browser"
        assert step.confidence == 0.60

    def test_terminal_command_without_capability_gets_cli(self):
        event = _make_event("command", "Ghostty", self._ts(), text_content="ls -la")
        step = classify_step(event, [], step_id=1)
        assert step.method == "cli"
        assert step.confidence == 0.70

    def test_shortcut_gets_macro(self):
        event = _make_event("shortcut", "SomeApp", self._ts(), shortcut="cmd+c")
        step = classify_step(event, [], step_id=1)
        assert step.method == "macro"
        assert step.confidence == 0.50

    def test_eliminate_takes_priority_over_everything(self):
        """Even with a capability match, app_switch should be eliminated."""
        cap = _make_cap("anything", "cli", [{"app": "Chrome"}])
        event = _make_event("app_switch", "Chrome", self._ts())
        step = classify_step(event, [cap], step_id=1)
        assert step.method == "eliminate"

    def test_wait_for_detected_before_capability(self):
        """A meaningful gap should produce wait_for even if capability matches."""
        from datetime import datetime, timezone, timedelta
        base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        prev_ts = base.isoformat().replace("+00:00", "")
        curr_ts = (base + timedelta(seconds=5)).isoformat().replace("+00:00", "")

        cap = _make_cap("anything", "cli", [{"app": "Ghostty"}])
        prev = _make_event("command", "Ghostty", prev_ts, id=1)
        curr = _make_event("command", "Ghostty", curr_ts, id=2)

        step = classify_step(curr, [cap], step_id=2, prev_event=prev)
        assert step.method == "wait_for"

    def test_step_id_set_correctly(self):
        event = _make_event("click", "Chrome", self._ts())
        step = classify_step(event, [], step_id=42)
        assert step.id == 42

    def test_original_field_populated(self):
        event = _make_event("command", "Ghostty", self._ts(), text_content="git status")
        step = classify_step(event, [], step_id=1)
        assert step.original != ""

    def test_mcp_capability_gets_api_method(self):
        cap = _make_cap("notion", "mcp", [{"url_contains": "notion.so"}])
        event = _make_event("click", "Chrome", self._ts(), window="My Page — notion.so")
        step = classify_step(event, [cap], step_id=1)
        assert step.method == "api"

    def test_applescript_capability_gets_macro_method(self):
        cap = _make_cap("applescript", "applescript", [{"app": "Finder"}])
        event = _make_event("click", "Finder", self._ts())
        step = classify_step(event, [cap], step_id=1)
        assert step.method == "macro"


# ---------------------------------------------------------------------------
# TestClassifyWorkflowSteps
# ---------------------------------------------------------------------------

class TestClassifyWorkflowSteps:
    def _ts(self, offset: float = 0) -> str:
        from datetime import datetime, timezone, timedelta
        base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        return (base + timedelta(seconds=offset)).isoformat().replace("+00:00", "")

    def _git_cap(self):
        return _make_cap("git", "cli", [{"command_contains": "git"}])

    def test_returns_list_of_steps(self):
        events = [
            _make_event("command", "Ghostty", self._ts(0), text_content="git status", id=1),
        ]
        steps = classify_workflow_steps(events, [self._git_cap()])
        assert isinstance(steps, list)
        assert len(steps) == 1

    def test_step_count_matches_event_count(self):
        events = [
            _make_event("command", "Ghostty", self._ts(0), text_content="git status", id=1),
            _make_event("app_switch", "Chrome", self._ts(1), id=2),
            _make_event("click", "Chrome", self._ts(2), id=3),
        ]
        steps = classify_workflow_steps(events, [self._git_cap()])
        assert len(steps) == 3

    def test_app_switch_classified_as_eliminate(self):
        events = [
            _make_event("command", "Ghostty", self._ts(0), text_content="git push", id=1),
            _make_event("app_switch", "Chrome", self._ts(1), id=2),
            _make_event("click", "Chrome", self._ts(2), id=3),
        ]
        steps = classify_workflow_steps(events, [self._git_cap()])
        assert steps[1].method == "eliminate"

    def test_git_command_classified_as_cli(self):
        events = [
            _make_event("command", "Ghostty", self._ts(0), text_content="git commit -m 'fix'", id=1),
        ]
        steps = classify_workflow_steps(events, [self._git_cap()])
        assert steps[0].method == "cli"
        assert steps[0].capability == "git"

    def test_browser_event_classified_as_browser(self):
        events = [
            _make_event("click", "Chrome", self._ts(0), id=1),
        ]
        steps = classify_workflow_steps(events, [])
        assert steps[0].method == "browser"

    def test_wait_for_detected_between_consecutive_events(self):
        events = [
            _make_event("click", "Chrome", self._ts(0), id=1),
            _make_event("click", "Chrome", self._ts(5.0), id=2),
        ]
        steps = classify_workflow_steps(events, [])
        assert steps[1].method == "wait_for"

    def test_mixed_workflow_methods(self):
        """A realistic workflow with multiple method types."""
        events = [
            _make_event("command", "Ghostty", self._ts(0), text_content="git status", id=1),
            _make_event("app_switch", "Chrome", self._ts(1), id=2),
            _make_event("click", "Chrome", self._ts(2), id=3),
            _make_event("command", "Ghostty", self._ts(3), text_content="npm run build", id=4),
            _make_event("shortcut", "SomeApp", self._ts(4), shortcut="cmd+s", id=5),
        ]
        steps = classify_workflow_steps(events, [self._git_cap()])
        methods = [s.method for s in steps]
        assert methods[0] in ("cli",)            # git command → cli via capability
        assert methods[1] == "eliminate"          # app_switch → eliminated
        assert methods[2] == "browser"            # chrome click → browser
        assert methods[3] == "cli"                # terminal command → cli
        assert methods[4] == "macro"              # shortcut → macro

    def test_step_ids_are_sequential(self):
        events = [
            _make_event("click", "Chrome", self._ts(0), id=1),
            _make_event("click", "Chrome", self._ts(1), id=2),
            _make_event("click", "Chrome", self._ts(2), id=3),
        ]
        steps = classify_workflow_steps(events, [])
        assert [s.id for s in steps] == [1, 2, 3]

    def test_empty_events_returns_empty_steps(self):
        steps = classify_workflow_steps([], [])
        assert steps == []

    def test_use_llm_false_skips_refinement(self):
        """With use_llm=False, low-confidence steps should not be refined."""
        events = [
            _make_event("unknown_type", "WeirdApp", self._ts(0), id=1),
        ]
        # Should not raise even though LLM would be called
        steps = classify_workflow_steps(events, [], use_llm=False)
        assert len(steps) == 1
        assert steps[0].method == "manual"
