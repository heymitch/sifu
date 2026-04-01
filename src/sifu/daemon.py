"""Sifu daemon interface — delegates capture to native SifuBar.app.

SifuBar.app (Swift) owns all macOS permissions and runs the capture
engine.  This module provides the CLI interface that communicates
with SifuBar via a command file (~/.sifu/command.json).
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import click

SIFU_DIR = Path.home() / ".sifu"
PID_FILE = SIFU_DIR / "sifubar.pid"
STATE_FILE = SIFU_DIR / "daemon.state"
COMMAND_FILE = SIFU_DIR / "command.json"
LOG_FILE = SIFU_DIR / "daemon.log"


# -- State helpers -----------------------------------------------------------

def _read_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _is_sifubar_running() -> bool:
    """Check if SifuBar is running via its PID file."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            pass
    return False


def _send_command(command: str):
    """Write a command to the command file for SifuBar to pick up."""
    SIFU_DIR.mkdir(parents=True, exist_ok=True)
    with open(COMMAND_FILE, "w") as f:
        json.dump({"command": command, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)


def _launch_sifubar():
    """Launch SifuBar.app if not already running."""
    if _is_sifubar_running():
        return True

    # Try to open the app bundle
    app_paths = [
        Path("/Applications/SifuBar.app"),
        Path.home() / "Applications" / "SifuBar.app",
        # Development: built from extras/SifuBar
        Path(__file__).parent.parent.parent / "extras" / "SifuBar" / ".build" / "release" / "SifuBar",
    ]

    for app_path in app_paths:
        if app_path.exists():
            if app_path.suffix == ".app":
                subprocess.Popen(["open", str(app_path)])
            else:
                subprocess.Popen(
                    [str(app_path)],
                    stdout=open(LOG_FILE, "a"),
                    stderr=open(LOG_FILE, "a"),
                    start_new_session=True,
                )
            # Wait briefly for it to start
            time.sleep(2)
            return True

    return False


# -- Public API (called from CLI) --------------------------------------------

def start_daemon():
    """Start capture via SifuBar."""
    state = _read_state()
    if state.get("status") in ("recording", "paused"):
        click.echo("Sifu is already running.")
        return

    if not _launch_sifubar():
        click.echo(
            "SifuBar not found. Install SifuBar.app or build from extras/SifuBar.\n"
            "  cd extras/SifuBar && swift build -c release"
        )
        return

    _send_command("start")
    click.echo("Sifu starting (via SifuBar).")


def stop_daemon():
    """Stop capture and launch analysis."""
    state = _read_state()
    if state.get("status") not in ("recording", "paused"):
        click.echo("Sifu is not running.")
        return

    _send_command("stop")
    click.echo("Sifu stopped.")

    # Auto-launch analysis
    click.echo("\nAnalyzing session...")
    _launch_analysis()


def _launch_analysis():
    """Run pattern detection -> compile SOPs -> coaching, all inline."""
    try:
        from sifu.patterns.engine import show_patterns
        show_patterns(today=True)
    except Exception as exc:
        click.echo(f"  Pattern detection: {exc}")

    click.echo("\nCompiling SOPs...")
    try:
        from sifu.compiler.sop import compile_workflows
        compile_workflows(today=True)
    except Exception as exc:
        click.echo(f"  Compile error: {exc}")

    click.echo("\nLaunching coach (background)...")
    log_fh = open(LOG_FILE, "a")
    subprocess.Popen(
        [sys.executable, "-c",
         "from sifu.coach.analyzer import run_coach; run_coach(today=True)"],
        stdout=log_fh, stderr=log_fh, start_new_session=True,
    )
    click.echo("  Coaching report building in background -> ~/.sifu/output/coach/")


def pause_daemon():
    """Pause capture."""
    if _read_state().get("status") != "recording":
        click.echo("Sifu is not recording.")
        return
    _send_command("pause")
    click.echo("Sifu paused.")


def resume_daemon():
    """Resume capture after pause."""
    if _read_state().get("status") != "paused":
        click.echo("Sifu is not paused.")
        return
    _send_command("resume")
    click.echo("Sifu resumed.")


def get_status(as_json=False):
    """Display daemon status and session stats."""
    state = _read_state()
    running = _is_sifubar_running()
    status = state.get("status", "stopped")

    info = {
        "running": running,
        "pid": state.get("pid"),
        "status": status,
        "session_id": state.get("session_id"),
        "start_time": state.get("start_time"),
        "steps": state.get("events", 0),
    }

    if info["start_time"]:
        from datetime import datetime
        start = datetime.fromisoformat(info["start_time"])
        info["duration_min"] = round((datetime.now() - start).total_seconds() / 60, 1)

    if as_json:
        click.echo(json.dumps(info))
    else:
        if running and status != "stopped":
            click.echo(f"  Status:   {status}")
            click.echo(f"  PID:      {info.get('pid', '?')}")
            click.echo(f"  Session:  {info.get('session_id', '?')}")
            click.echo(f"  Started:  {info.get('start_time', '?')}")
            click.echo(f"  Events:   {info.get('steps', 0)}")
            if "duration_min" in info:
                click.echo(f"  Duration: {info['duration_min']}m")
        else:
            click.echo("  Sifu is not running.")


def toggle_sensitive():
    """Pause capture and purge last N minutes."""
    if _read_state().get("status") not in ("recording", "paused"):
        click.echo("Sifu is not running.")
        return
    _send_command("sensitive")
    from sifu.config import get
    minutes = get("sensitive_purge_minutes", 5)
    click.echo(f"Purged last {minutes} minutes. Use 'sifu resume' to continue.")
