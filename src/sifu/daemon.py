"""CLI side of capture control: guards, messages, and post-stop analysis.

The capture process itself is reached through sifu.capture.
"""

import json
import subprocess
import sys

import click

from sifu.capture import LOG_FILE, Command, current_backend, is_running, read_state, send


def start_daemon():
    """Start capture via the platform's capture process."""
    if read_state().get("status") in ("recording", "paused"):
        click.echo("Sifu is already running.")
        return

    backend = current_backend()
    if backend is None:
        click.echo(f"No capture backend for {sys.platform} yet.")
        return
    if not (is_running(backend) or backend.launch()):
        click.echo(backend.install_hint)
        return

    send(Command.START)
    click.echo(f"Sifu starting (via {backend.name}).")


def stop_daemon():
    """Stop capture and launch analysis."""
    if read_state().get("status") not in ("recording", "paused"):
        click.echo("Sifu is not running.")
        return

    send(Command.STOP)
    click.echo("Sifu stopped.")

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
    if read_state().get("status") != "recording":
        click.echo("Sifu is not recording.")
        return
    send(Command.PAUSE)
    click.echo("Sifu paused.")


def resume_daemon():
    """Resume capture after pause."""
    if read_state().get("status") != "paused":
        click.echo("Sifu is not paused.")
        return
    send(Command.RESUME)
    click.echo("Sifu resumed.")


def get_status(as_json=False):
    """Display daemon status and session stats."""
    state = read_state()
    backend = current_backend()
    running = backend is not None and is_running(backend)
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
    if read_state().get("status") not in ("recording", "paused"):
        click.echo("Sifu is not running.")
        return
    send(Command.SENSITIVE)
    from sifu.config import get
    minutes = get("sensitive_purge_minutes", 5)
    click.echo(f"Purged last {minutes} minutes. Use 'sifu resume' to continue.")
