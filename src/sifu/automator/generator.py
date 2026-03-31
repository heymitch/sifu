"""Automator (Layer 4) — LLM-powered automation script generation from workflows.

Generates bash, browser (Playwright), AppleScript, computer-use, or Python
scripts from recorded workflow events. Scripts are saved to
~/.sifu/automations/<name>/ alongside a README.
"""

import os
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

AUTOMATIONS_DIR = Path.home() / ".sifu" / "automations"


# ── Script type detection ────────────────────────────────────────────────────

BROWSER_APPS = {"Chrome", "Safari", "Firefox", "Arc", "Brave", "Edge"}
TERMINAL_APPS = {"Ghostty", "Terminal", "iTerm2", "Warp", "Alacritty", "kitty"}
MACOS_APPS = {"Finder", "Mail", "Calendar", "Notes", "Preview"}

SCRIPT_TYPE_INSTRUCTIONS = {
    "bash": (
        "Generate a bash script that automates this workflow. "
        "Include set -euo pipefail, comments for each step, and variable "
        "substitution where appropriate."
    ),
    "browser": (
        "Generate a Python script using playwright "
        "(from playwright.sync_api import sync_playwright) that automates "
        "this browser workflow. Include proper wait conditions and error handling."
    ),
    "applescript": (
        "Generate an AppleScript that automates this macOS application workflow. "
        "Use 'tell application' blocks and proper delays."
    ),
    "computer_use": (
        "Generate a Python script that automates this cross-application workflow "
        "using subprocess and pyautogui. Include proper waits between steps."
    ),
    "python": (
        "Generate a Python script that automates this workflow. "
        "Use subprocess for shell commands and appropriate libraries for other actions."
    ),
}

SCRIPT_EXTENSIONS = {
    "bash": ".sh",
    "browser": ".py",
    "applescript": ".scpt",
    "computer_use": ".py",
    "python": ".py",
}


def _detect_script_type(events) -> str:
    """Determine the best script type for a workflow."""
    types = Counter(_get(e, "type") for e in events)
    apps = {_get(e, "app") for e in events if _get(e, "app")}

    # Pure terminal commands → bash script
    if apps.issubset(TERMINAL_APPS) and types.get("command", 0) > 0:
        return "bash"

    # Pure browser actions → Playwright script
    if apps and apps.issubset(BROWSER_APPS):
        return "browser"

    # macOS native apps (1-2 apps max) → AppleScript
    if apps.intersection(MACOS_APPS) and len(apps) <= 2:
        return "applescript"

    # Multi-app or mixed → computer use / Python with pyautogui
    if len(apps) > 2:
        return "computer_use"

    # Default → Python
    return "python"


# ── Prompt building ──────────────────────────────────────────────────────────


def _build_generation_prompt(events, script_type: str) -> str:
    """Build the Claude prompt for script generation."""
    lines = [
        f"Generate an automation script ({script_type}) for this recorded workflow.",
        SCRIPT_TYPE_INSTRUCTIONS[script_type],
        "The script should be immediately runnable with no modifications.",
        "Include a shebang line and make it self-documenting with comments.",
        "",
        "Recorded workflow:",
        "---",
    ]

    for i, e in enumerate(events, 1):
        ts_raw = _get(e, "timestamp")
        ts = ts_raw[11:19] if ts_raw else "?"
        app = _get(e, "app") or "?"
        etype = _get(e, "type") or "event"

        parts = [f"[{ts}]", f"({app})"]

        if etype == "command":
            parts.append(f"ran: {_get(e, 'text_content')}")
        elif etype == "shortcut":
            parts.append(f"pressed: {_get(e, 'shortcut')}")
        elif etype == "click":
            element = _get(e, "element") or _get(e, "description") or "unknown"
            x = _get(e, "position_x")
            y = _get(e, "position_y")
            parts.append(f"clicked: {element} at ({x},{y})")
        elif etype == "text_input":
            parts.append(f"typed: {_get(e, 'text_content')}")
        else:
            parts.append(etype)

        lines.append(f"  {i}. {' '.join(str(p) for p in parts)}")

    lines.append("---")
    lines.append(f"\nOutput ONLY the {script_type} script, no markdown fences or explanation.")
    return "\n".join(lines)


# ── README generation ────────────────────────────────────────────────────────


def _build_readme(workflow_id: str, events: list, script_type: str, script_filename: str) -> str:
    """Generate a README.md for the automation directory."""
    apps = sorted({_get(e, "app") for e in events if _get(e, "app")})
    duration = _estimate_duration(events)

    return f"""# Automation: {workflow_id}

**Type**: {script_type}
**Apps**: {', '.join(apps)}
**Steps**: {len(events)}
**Estimated time saved**: {duration}

## Usage

```bash
./{script_filename}
```

## Generated from

Workflow `{workflow_id}` captured by Sifu.
Review the script before running — it was AI-generated from your recorded actions.
"""


# ── Core generation ──────────────────────────────────────────────────────────


def generate_automation(workflow_id: str) -> Path:
    """Generate an automation script for a workflow.

    Fetches events for the given workflow_id, detects the best script type,
    calls Claude CLI to generate the script, saves it to
    ~/.sifu/automations/<slug>/, and returns the automation directory path.
    """
    import click
    from sifu.storage.db import get_connection, get_events_by_workflow

    conn = get_connection()
    rows = get_events_by_workflow(conn, workflow_id)
    conn.close()

    events = list(rows)
    if not events:
        raise ValueError(f"No events found for workflow '{workflow_id}'")

    script_type = _detect_script_type(events)
    click.echo(f"  Detected script type: {script_type}")

    prompt = _build_generation_prompt(events, script_type)

    click.echo("  Calling Claude to generate script...")
    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI failed: {result.stderr.strip()}")

    script_content = result.stdout.strip()
    if not script_content:
        raise RuntimeError("Claude returned an empty script.")

    # Save to automations directory
    name = _slugify(workflow_id)
    automation_dir = AUTOMATIONS_DIR / name
    automation_dir.mkdir(parents=True, exist_ok=True)

    ext = SCRIPT_EXTENSIONS.get(script_type, ".py")
    script_path = automation_dir / f"run{ext}"
    script_path.write_text(script_content)
    os.chmod(script_path, 0o755)

    readme = _build_readme(workflow_id, events, script_type, script_path.name)
    (automation_dir / "README.md").write_text(readme)

    return automation_dir


# ── Run saved automation ─────────────────────────────────────────────────────


def run_automation(name: str):
    """Run a saved automation by name."""
    import click

    automation_dir = AUTOMATIONS_DIR / name
    if not automation_dir.exists():
        click.echo(f"Automation '{name}' not found.")
        click.echo(f"  Looked in: {automation_dir}")
        return

    scripts = list(automation_dir.glob("run.*"))
    if not scripts:
        click.echo(f"No script found in {automation_dir}")
        return

    script = scripts[0]
    click.echo(f"Running {script}...")

    result = subprocess.run(
        [str(script)],
        capture_output=True,
        text=True,
    )

    if result.stdout:
        click.echo(result.stdout)
    if result.stderr:
        click.echo(result.stderr)

    if result.returncode != 0:
        click.echo(f"Script exited with code {result.returncode}.")


# ── List automations ─────────────────────────────────────────────────────────


def list_automations():
    """List all saved automations."""
    import click

    if not AUTOMATIONS_DIR.exists():
        click.echo(
            "No automations generated yet. "
            "Run 'sifu automate --generate <workflow>' first."
        )
        return

    dirs = sorted(d for d in AUTOMATIONS_DIR.iterdir() if d.is_dir())
    if not dirs:
        click.echo("No automations found.")
        return

    click.echo(f"\n  {len(dirs)} saved automation(s):\n")
    for d in dirs:
        readme = d / "README.md"
        type_line = ""
        if readme.exists():
            for line in readme.read_text().splitlines():
                if line.startswith("**Type**"):
                    type_line = line
                    break
        click.echo(f"  {d.name:30s}  {type_line}")

    click.echo()


# ── Candidate display ─────────────────────────────────────────────────────────


def _show_candidates():
    """Show workflows that are good automation candidates."""
    import click
    from sifu.patterns.engine import detect_patterns

    segments = detect_patterns()
    candidates = [s for s in segments if s.get("automation_candidate")]

    if not candidates:
        click.echo(
            "No automation candidates found. Record more workflows first."
        )
        return

    click.echo(f"\n  {len(candidates)} automation candidate(s):\n")
    for seg in candidates:
        click.echo(f"  {seg['workflow_id']}  {seg['title']}")
        click.echo(
            f"    Repeated {seg['pattern_count']}x  |  {seg['event_count']} steps"
        )
        click.echo(f"    Generate: sifu automate --generate {seg['workflow_id']}")
        click.echo()


# ── CLI entry point ───────────────────────────────────────────────────────────


def handle_automate(
    workflow_id: Optional[str] = None,
    automation_name: Optional[str] = None,
    list_all: bool = False,
):
    """CLI entry point for automation management."""
    import click

    if list_all:
        list_automations()
    elif workflow_id:
        path = generate_automation(workflow_id)
        click.echo(f"Generated: {path}")
    elif automation_name:
        run_automation(automation_name)
    else:
        _show_candidates()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get(event, key: str):
    """Uniform field access for sqlite3.Row or plain dict."""
    try:
        return event[key]
    except (KeyError, IndexError, TypeError):
        return None


def _slugify(text: str) -> str:
    """Convert a workflow ID to a filesystem-safe directory name."""
    return re.sub(r"[^a-z0-9-]", "-", text.lower()).strip("-")


def _estimate_duration(events: list) -> str:
    """Estimate the wall-clock time the workflow takes to run."""
    if len(events) < 2:
        return "< 1 minute"

    start_raw = _get(events[0], "timestamp")
    end_raw = _get(events[-1], "timestamp")
    if not start_raw or not end_raw:
        return "< 1 minute"

    start = datetime.fromisoformat(start_raw)
    end = datetime.fromisoformat(end_raw)
    minutes = (end - start).total_seconds() / 60

    if minutes < 1:
        return "< 1 minute"
    return f"~{minutes:.0f} minute(s)"
