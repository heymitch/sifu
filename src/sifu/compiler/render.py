"""Deterministic workflow-markdown renderer (Layer 2, no LLM).

Pure: rows in, structured markdown out. Replaces the compile-time `claude -p`
call — the summarizing/skill-decomposition now happens in the user's own agent
when they copy the staged collection. See
docs/superpowers/specs/2026-06-05-copy-to-agent-skill-decomposition.md.
"""

from datetime import datetime

from sifu.compiler.macro import build_macro
from sifu.compiler.meta import build_meta


def _pretty_time(ts):
    try:
        return datetime.fromisoformat(ts).strftime("%-I:%M %p")
    except (ValueError, TypeError):
        return ""


def _pretty_duration(seconds):
    if not seconds:
        return "0s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s" if m else f"{s}s"


def _describe(step):
    action = step.get("action")
    if action == "type" and step.get("text"):
        return f"Typed: {step['text']}"
    if action == "key" and step.get("key"):
        return f"Pressed {step['key']}"
    if action == "app_switch":
        return f"Switched to {step.get('app')}"
    return "Clicked"


def render_workflow_md(workflow_id, rows):
    macro = build_macro(workflow_id, rows)
    meta = build_meta(workflow_id, rows)
    apps = meta.get("app_set") or []
    title = ", ".join(apps) if apps else workflow_id
    out = f"# Workflow: {title}\n\n"
    out += (f"{_pretty_duration(meta.get('duration_seconds'))} · "
            f"{meta.get('step_count', len(rows))} steps · {', '.join(apps)}\n")
    for step in macro["steps"]:
        n = step["index"] + 1
        app = step.get("app") or "?"
        ts = _pretty_time(dict(rows[step["index"]]).get("timestamp"))
        head = f"\n## Step {n} — {app}" + (f" · {ts}" if ts else "")
        out += f"{head}\n{_describe(step)}\n"
        if step.get("screenshot"):
            out += f"![step {n}]({step['screenshot']})\n"
    return out
