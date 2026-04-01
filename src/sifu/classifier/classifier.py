"""Two-phase classifier engine — rule-based + optional LLM refinement."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from typing import Optional

from sifu.classifier.discovery import Capability
from sifu.classifier.spec import Step, WorkflowSpec, METHOD_TIERS
from sifu.storage.db import get_connection, get_events_by_workflow

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BROWSER_APPS = {"Chrome", "Safari", "Firefox", "Arc", "Brave", "Edge", "Brave Browser"}
TERMINAL_APPS = {"Ghostty", "Terminal", "iTerm2", "Warp", "Alacritty", "kitty"}
WAIT_FOR_THRESHOLD = 2.0   # seconds — minimum gap to flag as wait
WAIT_FOR_MAX = 60.0        # seconds — beyond this it's idle, not a wait


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------

def _match_capability(event: dict, cap: Capability) -> bool:
    """Return True if the event matches any of the capability's match patterns.

    Supported pattern keys:
    - app: exact match on event["app"]
    - command_contains: substring of event["text_content"]
    - url_contains: substring of event["window"]
    - mcp_server: lowercase name appears in event["app"] (lowercased)
    """
    app = event.get("app") or ""
    text = event.get("text_content") or ""
    window = event.get("window") or ""

    for pattern in cap.matches:
        if "app" in pattern:
            if app == pattern["app"]:
                return True
        if "command_contains" in pattern:
            if pattern["command_contains"].lower() in text.lower():
                return True
        if "url_contains" in pattern:
            if pattern["url_contains"].lower() in window.lower():
                return True
        if "mcp_server" in pattern:
            if pattern["mcp_server"].lower() in app.lower():
                return True

    return False


def _time_gap(e1: dict, e2: dict) -> float:
    """Return seconds between two events (e2 - e1). Returns 0.0 on parse error."""
    try:
        t1 = datetime.fromisoformat(e1["timestamp"])
        t2 = datetime.fromisoformat(e2["timestamp"])
        return (t2 - t1).total_seconds()
    except (KeyError, TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Phase 1 detectors
# ---------------------------------------------------------------------------

def _detect_eliminate(
    event: dict,
    prev_event: Optional[dict],
    next_event: Optional[dict],
) -> Optional[str]:
    """Return a reason string if this step is pure overhead, else None.

    Eliminated types: app_switch, window_switch.
    """
    event_type = event.get("type", "")
    if event_type in ("app_switch", "window_switch"):
        return f"overhead: {event_type}"
    return None


def _detect_wait_for(
    event: dict,
    prev_event: Optional[dict],
) -> Optional[dict]:
    """Return a condition dict if there's a meaningful gap before this event.

    Criteria:
    - prev_event exists
    - Same app as prev_event
    - Gap is between WAIT_FOR_THRESHOLD and WAIT_FOR_MAX seconds

    Condition dict keys: type, app, estimated_wait
    """
    if prev_event is None:
        return None

    app = event.get("app") or ""
    prev_app = prev_event.get("app") or ""

    if app != prev_app:
        return None

    gap = _time_gap(prev_event, event)
    if gap < WAIT_FOR_THRESHOLD or gap > WAIT_FOR_MAX:
        return None

    # Determine wait condition type based on app category
    if app in BROWSER_APPS:
        condition_type = "page_loaded"
    elif app in TERMINAL_APPS:
        condition_type = "command_complete"
    else:
        condition_type = "app_ready"

    return {
        "type": condition_type,
        "app": app,
        "estimated_wait": round(gap, 1),
    }


# ---------------------------------------------------------------------------
# Core classification
# ---------------------------------------------------------------------------

def _capability_type_to_method(cap_type: str) -> str:
    """Map a capability type string to a METHOD_TIERS method name."""
    mapping = {
        "cli": "cli",
        "mcp": "api",
        "api": "api",
        "cli+api": "api",
        "browser": "browser",
        "applescript": "macro",
        "custom": "api",
    }
    return mapping.get(cap_type, "manual")


def _slugify(text: str) -> str:
    """Return a filesystem-safe slug from text."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = text.strip("-")
    return text or "step"


def _describe_event(event: dict) -> str:
    """Return a human-readable description of a raw event."""
    event_type = event.get("type", "unknown")
    app = event.get("app") or ""
    text = event.get("text_content") or ""
    shortcut = event.get("shortcut") or ""
    window = event.get("window") or ""

    if event_type == "command":
        cmd = text[:60] + ("…" if len(text) > 60 else "")
        return f"Run command in {app}: {cmd}" if app else f"Run command: {cmd}"
    if event_type in ("click", "left_click"):
        elem = event.get("element") or ""
        desc = elem or window or app
        return f"Click {desc}" if desc else "Click"
    if event_type == "shortcut":
        return f"Press {shortcut} in {app}" if app else f"Press {shortcut}"
    if event_type == "type":
        preview = text[:40] + ("…" if len(text) > 40 else "")
        return f"Type '{preview}' in {app}" if app else f"Type '{preview}'"
    if event_type == "app_switch":
        return f"Switch to {app}"
    if event_type == "window_switch":
        return f"Switch window in {app}"
    if event_type == "scroll":
        return f"Scroll in {app}" if app else "Scroll"

    desc = event.get("description") or ""
    if desc:
        return desc
    if text:
        return f"{event_type} in {app}: {text[:50]}" if app else f"{event_type}: {text[:50]}"
    return f"{event_type} in {app}" if app else event_type


def _describe_with_capability(event: dict, cap: Capability) -> str:
    """Return a description that names the matched capability."""
    base = _describe_event(event)
    return f"{base} (via {cap.name})"


def classify_step(
    event: dict,
    capabilities: list[Capability],
    step_id: int,
    prev_event: Optional[dict] = None,
    next_event: Optional[dict] = None,
) -> Step:
    """Classify a single event into a Step.

    Priority order:
    1. eliminate
    2. wait_for
    3. capability match
    4. generic terminal (cli)
    5. generic browser
    6. shortcut (macro)
    7. manual fallback
    """
    original = _describe_event(event)
    app = event.get("app") or ""
    event_type = event.get("type", "")

    # --- Priority 1: eliminate ---
    elim_reason = _detect_eliminate(event, prev_event, next_event)
    if elim_reason is not None:
        return Step(
            id=step_id,
            description=original,
            original=original,
            method="eliminate",
            confidence=0.90,
            reason=elim_reason,
        )

    # --- Priority 2: wait_for ---
    wait_condition = _detect_wait_for(event, prev_event)
    if wait_condition is not None:
        return Step(
            id=step_id,
            description=f"Wait for {wait_condition['type']} in {wait_condition['app']}",
            original=original,
            method="wait_for",
            confidence=0.75,
            condition=wait_condition,
        )

    # --- Priority 3: capability match ---
    for cap in capabilities:
        if _match_capability(event, cap):
            method = _capability_type_to_method(cap.type)
            desc = _describe_with_capability(event, cap)
            return Step(
                id=step_id,
                description=desc,
                original=original,
                method=method,
                confidence=0.85,
                capability=cap.name,
                tool=cap.name,
                action=event_type,
                command=event.get("text_content"),
            )

    # --- Priority 4: generic terminal (cli) ---
    if app in TERMINAL_APPS and event_type == "command":
        return Step(
            id=step_id,
            description=original,
            original=original,
            method="cli",
            confidence=0.70,
            command=event.get("text_content"),
        )

    # --- Priority 5: generic browser ---
    if app in BROWSER_APPS:
        return Step(
            id=step_id,
            description=original,
            original=original,
            method="browser",
            confidence=0.60,
            action=event_type,
        )

    # --- Priority 6: shortcut (macro) ---
    if event_type == "shortcut" or event.get("shortcut"):
        return Step(
            id=step_id,
            description=original,
            original=original,
            method="macro",
            confidence=0.50,
            command=event.get("shortcut"),
        )

    # --- Priority 7: manual fallback ---
    return Step(
        id=step_id,
        description=original,
        original=original,
        method="manual",
        confidence=0.30,
    )


def classify_workflow_steps(
    events: list[dict],
    capabilities: list[Capability],
    use_llm: bool = False,
) -> list[Step]:
    """Classify all events in a workflow and return a list of Steps."""
    steps: list[Step] = []

    for i, event in enumerate(events):
        prev_event = events[i - 1] if i > 0 else None
        next_event = events[i + 1] if i < len(events) - 1 else None
        step = classify_step(event, capabilities, step_id=i + 1, prev_event=prev_event, next_event=next_event)
        steps.append(step)

    if use_llm:
        _refine_with_llm(steps, events, capabilities)

    return steps


def classify_workflow(
    workflow_id: str,
    capabilities: list[Capability],
    use_llm: bool = True,
) -> WorkflowSpec:
    """Fetch events from DB, classify, and return a WorkflowSpec.

    Computes human stats (step count, unique apps, time span).
    """
    conn = get_connection()
    try:
        events = get_events_by_workflow(conn, workflow_id)
        # Convert sqlite3.Row objects to dicts for consistent access
        events = [dict(row) for row in events]
    finally:
        conn.close()

    steps = classify_workflow_steps(events, capabilities, use_llm=use_llm)

    # Compute human stats
    human_steps = len(events)
    apps = {e.get("app") for e in events if e.get("app")}
    human_apps = len(apps)

    human_time: Optional[str] = None
    if len(events) >= 2:
        try:
            t_start = datetime.fromisoformat(events[0]["timestamp"])
            t_end = datetime.fromisoformat(events[-1]["timestamp"])
            elapsed = (t_end - t_start).total_seconds()
            minutes, seconds = divmod(int(elapsed), 60)
            human_time = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
        except (KeyError, TypeError, ValueError):
            pass

    spec = WorkflowSpec(
        id=_slugify(workflow_id),
        source_workflow=workflow_id,
        steps=steps,
        capabilities_snapshot=[cap.name for cap in capabilities],
        human_steps=human_steps,
        human_apps=human_apps,
        human_time=human_time,
    )

    return spec


# ---------------------------------------------------------------------------
# Phase 2: LLM refinement
# ---------------------------------------------------------------------------

def _refine_with_llm(
    steps: list[Step],
    events: list[dict],
    capabilities: list[Capability],
) -> None:
    """Refine uncertain steps (confidence < 0.7) using Claude CLI.

    Builds a prompt listing available capabilities and uncertain steps,
    calls `claude -p` via subprocess, parses JSON response, and updates
    steps in-place if the LLM returns higher confidence.
    """
    uncertain_indices = [i for i, s in enumerate(steps) if s.confidence < 0.7]
    if not uncertain_indices:
        return

    # Build prompt
    cap_list = "\n".join(
        f"- {cap.name} ({cap.type}): {cap.description}" for cap in capabilities
    )

    uncertain_steps_text = ""
    for idx in uncertain_indices:
        s = steps[idx]
        e = events[idx] if idx < len(events) else {}
        uncertain_steps_text += (
            f"\nStep {s.id}:\n"
            f"  original: {s.original}\n"
            f"  current method: {s.method}\n"
            f"  current confidence: {s.confidence}\n"
            f"  event type: {e.get('type', 'unknown')}\n"
            f"  app: {e.get('app', '')}\n"
            f"  text: {e.get('text_content', '')}\n"
        )

    prompt = f"""You are classifying workflow steps for automation.

Available capabilities:
{cap_list}

METHOD_TIERS (from most to least automated): eliminate, wait_for, poll, api, cli, browser, macro, manual

Classify these uncertain steps. For each step, return the best method and confidence (0.0-1.0).

Uncertain steps:
{uncertain_steps_text}

Respond with ONLY a JSON array like:
[
  {{"step_id": 1, "method": "cli", "confidence": 0.85, "description": "improved description", "tool": "git"}},
  ...
]
Only include steps you can improve. If unsure, omit the step."""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        if not output:
            return

        # Extract JSON array from output
        match = re.search(r"\[.*\]", output, re.DOTALL)
        if not match:
            return

        refinements = json.loads(match.group())

        # Apply refinements
        step_by_id = {s.id: s for s in steps}
        for ref in refinements:
            step_id = ref.get("step_id")
            if step_id not in step_by_id:
                continue
            step = step_by_id[step_id]
            new_confidence = float(ref.get("confidence", 0))
            if new_confidence > step.confidence:
                step.method = ref.get("method", step.method)
                step.confidence = new_confidence
                if "description" in ref:
                    step.description = ref["description"]
                if "tool" in ref:
                    step.tool = ref["tool"]
                    step.capability = ref["tool"]

    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        # LLM refinement is best-effort — never fail the pipeline
        pass
