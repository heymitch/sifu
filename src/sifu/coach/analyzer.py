"""Layer 3: Coach — LLM-powered efficiency analysis."""

from __future__ import annotations

from collections import Counter


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_coach(today: bool = False, focus: str | None = None) -> None:
    """Generate a coaching report. Called from the CLI."""
    import click
    from datetime import datetime, timedelta
    from sifu.storage.db import get_connection, get_events_between

    conn = get_connection()

    if today:
        start = datetime.now().strftime("%Y-%m-%dT00:00:00")
        end = datetime.now().strftime("%Y-%m-%dT23:59:59")
    else:
        start = (datetime.now() - timedelta(days=7)).isoformat()
        end = datetime.now().isoformat()

    rows = get_events_between(conn, start, end)
    conn.close()

    # sqlite3.Row supports dict-style access; convert once for easier handling.
    events = [dict(r) for r in rows]

    if not events:
        click.echo("No events found for analysis.")
        return

    # --- Local analysis (fast, no LLM) ---
    findings: list[dict] = []
    if not focus or focus == "shortcuts":
        findings.extend(analyze_shortcuts(events))
    if not focus or focus == "redundant":
        findings.extend(analyze_redundant(events))
    if not focus or focus == "automation":
        findings.extend(analyze_automation(events))
    if not focus or focus == "tools":
        from sifu.coach.tools import suggest_tools
        findings.extend(suggest_tools(events))
    if not focus or focus == "workflow":
        findings.extend(analyze_workflow(events))

    # --- LLM deeper analysis ---
    llm_insights = _get_llm_insights(events, findings)

    # --- Output ---
    _display_report(findings, llm_insights, today)
    _save_report(findings, llm_insights)


# ---------------------------------------------------------------------------
# Local analysis functions
# ---------------------------------------------------------------------------


def analyze_shortcuts(events: list[dict]) -> list[dict]:
    """Find right-click → menu patterns where keyboard shortcuts would be faster."""
    findings: list[dict] = []

    shortcut_map = {
        "copy": "Cmd+C",
        "paste": "Cmd+V",
        "cut": "Cmd+X",
        "undo": "Cmd+Z",
        "redo": "Cmd+Shift+Z",
        "select all": "Cmd+A",
        "save": "Cmd+S",
    }

    for i in range(len(events) - 1):
        if events[i]["type"] == "right_click":
            next_e = events[i + 1]
            if next_e["type"] == "click" and next_e.get("element"):
                element = (next_e["element"] or "").lower()
                for action, shortcut in shortcut_map.items():
                    if action in element:
                        findings.append({
                            "category": "shortcuts",
                            "message": (
                                f"You used right-click → {action.title()}"
                                f" — try {shortcut} instead"
                            ),
                            "count": 1,
                            "severity": "low",
                        })

    return _aggregate_findings(findings)


def analyze_redundant(events: list[dict]) -> list[dict]:
    """Find apps switched to so frequently that a permanent arrangement makes sense."""
    findings: list[dict] = []

    app_switches = [e for e in events if e["type"] == "app_switch"]
    app_counts = Counter(e["app"] for e in app_switches if e.get("app"))

    for app, count in app_counts.most_common(5):
        if count > 10:
            findings.append({
                "category": "redundant",
                "message": (
                    f"You switched to {app} {count} times."
                    " Consider keeping it pinned or using split screen."
                ),
                "count": count,
                "severity": "medium",
            })

    return findings


def analyze_automation(events: list[dict]) -> list[dict]:
    """Find terminal commands repeated enough to warrant an alias or script."""
    findings: list[dict] = []

    commands = [
        e["text_content"]
        for e in events
        if e["type"] == "command" and e.get("text_content")
    ]
    cmd_counts = Counter(commands)

    for cmd, count in cmd_counts.most_common(10):
        if count >= 3:
            findings.append({
                "category": "automation",
                "message": f"You ran `{cmd}` {count} times. Consider aliasing it.",
                "count": count,
                "severity": "medium" if count < 5 else "high",
            })

    return findings


def analyze_workflow(events: list[dict]) -> list[dict]:
    """Detect frequent app-switch pairs that suggest a split-screen or unified tool."""
    findings: list[dict] = []

    pairs: Counter = Counter()
    for i in range(len(events) - 1):
        if events[i]["type"] == "app_switch" and events[i + 1]["type"] == "app_switch":
            pair = (
                events[i].get("app") or "?",
                events[i + 1].get("app") or "?",
            )
            pairs[pair] += 1

    for (app1, app2), count in pairs.most_common(5):
        if count > 15:
            findings.append({
                "category": "workflow",
                "message": (
                    f"You switch between {app1} and {app2} frequently ({count}x)."
                    " Consider split screen or a combined workflow."
                ),
                "count": count,
                "severity": "low",
            })

    return findings


# ---------------------------------------------------------------------------
# LLM analysis
# ---------------------------------------------------------------------------


def _get_llm_insights(events: list[dict], local_findings: list[dict]) -> str:
    """Send a compact workflow summary to Claude CLI for deeper insights."""
    import subprocess

    lines = [
        "Analyze this user's workflow data and provide efficiency coaching.",
        "Focus on actionable suggestions they can implement today.",
        f"Total events: {len(events)}",
        f"Local findings: {len(local_findings)}",
        "",
        "Event type breakdown:",
    ]

    type_counts = Counter(e["type"] for e in events)
    for t, c in type_counts.most_common():
        lines.append(f"  {t}: {c}")

    lines.append("\nApp usage:")
    app_counts = Counter(e["app"] for e in events if e.get("app"))
    for a, c in app_counts.most_common(10):
        lines.append(f"  {a}: {c} events")

    lines.append("\nLocal analysis already found:")
    for f in local_findings:
        lines.append(f"  - [{f['category']}] {f['message']}")

    lines.append(
        "\nProvide 3-5 additional insights not covered by the local analysis above."
    )

    prompt = "\n".join(lines)

    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return ""


# ---------------------------------------------------------------------------
# Report display and persistence
# ---------------------------------------------------------------------------

_SEVERITY_ICON = {"low": "·", "medium": "▸", "high": "▸▸"}


def _display_report(
    findings: list[dict], llm_insights: str, today: bool
) -> None:
    import click

    period = "today" if today else "this week"
    click.echo(f"\n  ═══ Sifu Coach — {period} ═══\n")

    if findings:
        by_cat: dict[str, list[dict]] = {}
        for f in findings:
            by_cat.setdefault(f["category"], []).append(f)

        for cat, items in by_cat.items():
            click.echo(f"  ── {cat.upper()} ──")
            for item in items:
                icon = _SEVERITY_ICON.get(item.get("severity", "low"), "·")
                click.echo(f"  {icon} {item['message']}")
            click.echo()
    else:
        click.echo("  No local findings.\n")

    if llm_insights:
        click.echo("  ── AI INSIGHTS ──")
        # Indent each line of the LLM output for consistent formatting.
        for line in llm_insights.splitlines():
            click.echo(f"  {line}" if line.strip() else "")
        click.echo()


def _save_report(findings: list[dict], llm_insights: str) -> None:
    import json
    from pathlib import Path
    from datetime import datetime

    report_dir = Path.home() / ".sifu" / "output" / "coach"
    report_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "date": datetime.now().isoformat(),
        "findings": findings,
        "llm_insights": llm_insights,
    }

    path = report_dir / f"coach-{datetime.now().strftime('%Y-%m-%d')}.json"
    with open(path, "w") as fh:
        json.dump(report, fh, indent=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _aggregate_findings(findings: list[dict]) -> list[dict]:
    """Merge duplicate findings by message, summing their counts."""
    merged: dict[str, dict] = {}
    for f in findings:
        key = f["message"]
        if key in merged:
            merged[key]["count"] += f["count"]
        else:
            merged[key] = f.copy()
    return list(merged.values())
