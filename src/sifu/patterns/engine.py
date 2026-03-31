"""Pattern Engine (Layer 1) — local sequence detection and workflow segmentation.

No LLM. Runs locally on raw events from SQLite and produces workflow segments
with repeated-sequence detection. Results are written to disk and workflow IDs
are written back to the events table.
"""

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

PATTERNS_DIR = Path.home() / ".sifu" / "output" / "patterns"

# ── Segmentation boundaries ──────────────────────────────────────────────────

APP_SWITCH_GAP = 30   # seconds: app switch + gap > this → new segment
IDLE_GAP = 300        # seconds: gap >= this → session boundary


# ── Public API ───────────────────────────────────────────────────────────────


def show_patterns(today: bool = False, app: Optional[str] = None) -> None:
    """Display detected patterns. Called from CLI."""
    import click
    from sifu.storage.db import get_connection, get_events_between

    conn = get_connection()

    if today:
        start = datetime.now().strftime("%Y-%m-%dT00:00:00")
        end = datetime.now().strftime("%Y-%m-%dT23:59:59")
    else:
        start = (datetime.now() - timedelta(days=7)).isoformat()
        end = datetime.now().isoformat()

    events = get_events_between(conn, start, end, app=app)
    conn.close()

    if not events:
        click.echo("No events found.")
        return

    segments = detect_patterns(events=list(events))

    label = "today" if today else "last 7 days"
    app_label = f" in {app}" if app else ""
    click.echo(f"\n  Found {len(segments)} workflow segment(s) ({label}{app_label}):\n")

    for seg in segments:
        marker = " \u2605" if seg["automation_candidate"] else ""
        click.echo(f"  {seg['workflow_id']}  {seg['title']}{marker}")
        click.echo(
            f"    {seg['event_count']} steps  |  "
            f"{seg['start_time'][11:19]} \u2014 {seg['end_time'][11:19]}  |  "
            f"{seg['app']}"
        )
        if seg["pattern_count"] > 0:
            click.echo(
                f"    Pattern repeated {seg['pattern_count']}x \u2014 automation candidate"
            )
        click.echo()


def detect_patterns(
    session_id: Optional[str] = None,
    events: Optional[list] = None,
) -> list[dict]:
    """Run pattern detection on events and return list of workflow segments.

    Optionally accepts a pre-fetched list of events (list of sqlite3.Row or
    dicts). When events is None, loads from DB filtered by session_id (or all
    events if session_id is also None).

    Side-effects:
      - Writes pattern JSON to ~/.sifu/output/patterns/patterns-YYYY-MM-DD.json
      - Updates workflow_id on matched events in the DB
    """
    from sifu.storage.db import get_connection, get_events_between, update_workflow_id

    if events is None:
        conn = get_connection()
        if session_id:
            from sifu.storage.db import get_events_by_session
            rows = get_events_by_session(conn, session_id)
        else:
            # All events, ordered ASC (get_events_between uses ORDER BY timestamp ASC)
            start = "1970-01-01T00:00:00"
            end = datetime.now().isoformat()
            rows = get_events_between(conn, start, end)
        events = list(rows)
        conn.close()

    if not events:
        return []

    segments = segment_workflows(events)

    # Write workflow IDs back to DB and persist patterns to disk
    conn = get_connection()
    for seg in segments:
        if seg["event_ids"]:
            update_workflow_id(conn, seg["event_ids"], seg["workflow_id"])
    conn.close()

    _save_patterns(segments)

    return segments


def segment_workflows(events: list) -> list[dict]:
    """Group a flat, time-ordered event list into workflow segments.

    Segmentation rules (from PRD):
      1. App switch with >30 s gap  → new segment boundary
      2. 5+ minute idle             → session boundary
      3. Repeated sequence (3+ steps, same app, appears 2+ times) → flagged
      4. Terminal command clusters  → kept together (handled implicitly by
         the app-switch rule since they stay in the same terminal app)
    """
    if not events:
        return []

    segments: list[dict] = []
    current_segment: list = []
    _counter = [0]  # mutable so inner helper can increment

    def flush(seg_events: list) -> None:
        if seg_events:
            _counter[0] += 1
            segments.append(_make_segment(seg_events, _counter[0]))

    for i, event in enumerate(events):
        if i == 0:
            current_segment.append(event)
            continue

        gap = _time_gap(events[i - 1], event)
        app_switched = _get(event, "app") != _get(events[i - 1], "app")

        # Session boundary: idle ≥ 5 minutes
        if gap >= IDLE_GAP:
            flush(current_segment)
            current_segment = [event]
            continue

        # Segment boundary: app switch with gap > 30 s
        if app_switched and gap > APP_SWITCH_GAP:
            flush(current_segment)
            current_segment = [event]
            continue

        current_segment.append(event)

    flush(current_segment)

    _detect_repeated_sequences(segments)

    return segments


# ── Internal helpers ─────────────────────────────────────────────────────────


def _get(event, key: str):
    """Uniform field access for sqlite3.Row or plain dict."""
    try:
        return event[key]
    except (KeyError, IndexError):
        return None


def _time_gap(e1, e2) -> float:
    """Seconds between two events (always non-negative)."""
    t1_raw = _get(e1, "timestamp")
    t2_raw = _get(e2, "timestamp")
    if not t1_raw or not t2_raw:
        return 0.0
    t1 = datetime.fromisoformat(t1_raw)
    t2 = datetime.fromisoformat(t2_raw)
    return abs((t2 - t1).total_seconds())


def _primary_app(events: list) -> str:
    """Most common (non-null) app in an event list."""
    apps = [_get(e, "app") for e in events if _get(e, "app")]
    if not apps:
        return "Unknown"
    return Counter(apps).most_common(1)[0][0]


def _generate_title(events: list) -> str:
    """Auto-generate a human-readable segment title from the first 4 events."""
    app = _primary_app(events)
    actions: list[str] = []

    for e in events[:4]:
        etype = _get(e, "type") or "event"
        if etype == "command":
            raw = _get(e, "text_content") or ""
            cmd = raw.split()[0] if raw.strip() else "cmd"
            actions.append(cmd)
        elif etype == "shortcut":
            actions.append(_get(e, "shortcut") or "shortcut")
        else:
            actions.append(etype)

    summary = " \u2192 ".join(actions)
    if len(events) > 4:
        summary += f" \u2192 ...({len(events)} steps)"

    return f"auto: {app} \u2014 {summary}"


def _make_segment(events: list, counter: int) -> dict:
    """Build a workflow segment dict from a list of events."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    workflow_id = f"wf-{date_str}-{counter:03d}"

    # Collect unique event types present in this segment
    types = list({_get(e, "type") for e in events if _get(e, "type")})

    return {
        "workflow_id": workflow_id,
        "title": _generate_title(events),
        "app": _primary_app(events),
        "event_ids": [_get(e, "id") for e in events if _get(e, "id") is not None],
        "event_count": len(events),
        "start_time": _get(events[0], "timestamp") or "",
        "end_time": _get(events[-1], "timestamp") or "",
        "types": types,
        "pattern_count": 0,
        "automation_candidate": False,
    }


def _detect_repeated_sequences(segments: list[dict]) -> None:
    """Find segments whose (type, app) action sequence appears 2+ times.

    Mutates segments in-place: sets pattern_count and automation_candidate.

    A "signature" is the tuple of (event_type, app) pairs for every event in
    the segment, taken from the original event list reconstructed via the DB.
    Because we only have event_ids here (not the raw events), we use the
    segment-level metadata that was already computed: the ordered type/app
    sequence can be approximated from (types, app) for a lightweight check.

    For a stronger signal we reconstruct the per-event sequence from the DB.
    """
    from sifu.storage.db import get_connection, get_events_by_workflow

    conn = get_connection()

    signatures: dict[tuple, list[dict]] = {}

    for seg in segments:
        wf_id = seg["workflow_id"]
        # Fetch the events we just assigned this workflow_id
        rows = get_events_by_workflow(conn, wf_id)

        if len(rows) < 3:
            continue

        sig = tuple(
            (_get(r, "type") or "", _get(r, "app") or "") for r in rows
        )
        signatures.setdefault(sig, []).append(seg)

    conn.close()

    for sig, matching in signatures.items():
        if len(matching) >= 2:
            for seg in matching:
                seg["pattern_count"] = len(matching)
                seg["automation_candidate"] = True


def _save_patterns(segments: list[dict]) -> None:
    """Persist segments as JSON in ~/.sifu/output/patterns/patterns-YYYY-MM-DD.json."""
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = PATTERNS_DIR / f"patterns-{date_str}.json"

    # Merge with any existing patterns file for today so incremental runs
    # don't erase earlier results.
    existing: list[dict] = []
    if path.exists():
        try:
            with open(path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = []

    # Deduplicate by workflow_id: new segments overwrite old ones with same id
    by_id: dict[str, dict] = {s["workflow_id"]: s for s in existing}
    for seg in segments:
        by_id[seg["workflow_id"]] = seg

    merged = sorted(by_id.values(), key=lambda s: s.get("start_time", ""))

    with open(path, "w") as f:
        json.dump(merged, f, indent=2)
