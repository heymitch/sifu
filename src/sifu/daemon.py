"""Sifu capture daemon — Layer 0.

Spawns a background process (via subprocess, NOT fork) that captures user
actions via macOS CGEventTap and Accessibility APIs.  The parent writes a
PID file and returns immediately so the CLI stays snappy.

macOS Cocoa/CoreFoundation frameworks are not fork-safe, so we use
subprocess.Popen to launch a clean Python process for the capture loop.
"""

import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import click

SIFU_DIR = Path.home() / ".sifu"
PID_FILE = SIFU_DIR / "daemon.pid"
STATE_FILE = SIFU_DIR / "daemon.state"
LOG_FILE = SIFU_DIR / "daemon.log"


# ── State helpers ───────────────────────────────────────


def _read_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def _write_state(state: dict):
    SIFU_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def _is_running() -> tuple[bool, int | None]:
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)  # check if alive
            return True, pid
        except (OSError, ValueError):
            PID_FILE.unlink(missing_ok=True)
    return False, None


# ── Public API (called from CLI) ────────────────────────


def start_daemon():
    """Start the capture daemon as a background process."""
    running, pid = _is_running()
    if running:
        click.echo(f"Sifu is already running (PID {pid}).")
        return

    from sifu.storage.db import init_db, create_session

    SIFU_DIR.mkdir(parents=True, exist_ok=True)
    conn = init_db()

    session_id = f"session-{uuid.uuid4().hex[:8]}"
    start_time = time.strftime("%Y-%m-%dT%H:%M:%S")
    create_session(conn, session_id, start_time)
    conn.close()

    _write_state({
        "status": "recording",
        "session_id": session_id,
        "start_time": start_time,
        "events": 0,
    })

    # Spawn a clean process — do NOT fork (macOS Cocoa is not fork-safe)
    log_fh = open(LOG_FILE, "a")
    proc = subprocess.Popen(
        [sys.executable, "-m", "sifu.daemon", session_id],
        stdout=log_fh,
        stderr=log_fh,
        start_new_session=True,
    )

    PID_FILE.write_text(str(proc.pid))
    click.echo(f"Sifu started (PID {proc.pid}).  Session: {session_id}")


def stop_daemon():
    """Stop the capture daemon."""
    running, pid = _is_running()
    if not running:
        click.echo("Sifu is not running.")
        return
    os.kill(pid, signal.SIGTERM)
    PID_FILE.unlink(missing_ok=True)
    _write_state({"status": "stopped"})
    click.echo("Sifu stopped.")


def pause_daemon():
    """Pause capture (events still arrive but are discarded)."""
    running, pid = _is_running()
    if not running:
        click.echo("Sifu is not running.")
        return
    state = _read_state()
    state["status"] = "paused"
    _write_state(state)
    os.kill(pid, signal.SIGUSR1)
    click.echo("Sifu paused.")


def resume_daemon():
    """Resume capture after a pause."""
    running, pid = _is_running()
    if not running:
        click.echo("Sifu is not running.")
        return
    state = _read_state()
    state["status"] = "recording"
    _write_state(state)
    os.kill(pid, signal.SIGUSR2)
    click.echo("Sifu resumed.")


def get_status(as_json=False):
    """Display daemon status and session stats."""
    running, pid = _is_running()
    state = _read_state()

    info = {
        "running": running,
        "pid": pid,
        "status": state.get("status", "stopped"),
        "session_id": state.get("session_id"),
        "start_time": state.get("start_time"),
        "steps": state.get("events", 0),
    }

    if info["start_time"]:
        from datetime import datetime

        start = datetime.fromisoformat(info["start_time"])
        info["duration_min"] = round(
            (datetime.now() - start).total_seconds() / 60, 1
        )

    if as_json:
        click.echo(json.dumps(info))
    else:
        if running:
            click.echo(f"  Status:   {info['status']}")
            click.echo(f"  PID:      {pid}")
            click.echo(f"  Session:  {info.get('session_id', '?')}")
            click.echo(f"  Started:  {info.get('start_time', '?')}")
            click.echo(f"  Events:   {info.get('steps', 0)}")
            if "duration_min" in info:
                click.echo(f"  Duration: {info['duration_min']}m")
        else:
            click.echo("  Sifu is not running.")


def toggle_sensitive():
    """Pause capture and purge the last N minutes of events + screenshots."""
    running, _ = _is_running()
    if not running:
        click.echo("Sifu is not running.")
        return

    pause_daemon()

    from sifu.config import get
    from sifu.storage.db import get_connection, purge_recent
    from sifu.storage.disk import delete_screenshot

    minutes = get("sensitive_purge_minutes", 5)
    conn = get_connection()
    screenshot_paths = purge_recent(conn, minutes)
    conn.close()

    for path in screenshot_paths:
        delete_screenshot(path)

    click.echo(
        f"Purged last {minutes} minutes.  Use 'sifu resume' to continue."
    )


# ── Capture loop (runs in spawned child process) ────────


_paused = False


def _run_capture_loop(session_id: str):
    """Main capture loop — sets up event taps and enters CFRunLoop."""
    from sifu.storage.db import init_db
    from sifu.capture.mouse import MouseCapture
    from sifu.capture.keyboard import KeyboardCapture
    from sifu.capture.apps import AppTracker
    from sifu.capture.screenshots import ScreenshotCapture
    from sifu.config import load_config

    conn = init_db()
    config = load_config()
    screenshot = ScreenshotCapture(config)

    mouse = MouseCapture(conn, session_id, config)
    keyboard = KeyboardCapture(conn, session_id, config)
    app_tracker = AppTracker(conn, session_id, config)

    # ── Signal handlers ──────────────────────────────────

    def _handle_stop(signum, frame):
        mouse.stop()
        keyboard.stop()
        app_tracker.stop()
        from sifu.storage.db import end_session

        end_session(conn, session_id, time.strftime("%Y-%m-%dT%H:%M:%S"))
        PID_FILE.unlink(missing_ok=True)
        _write_state({"status": "stopped"})
        sys.exit(0)

    def _handle_pause(signum, frame):
        global _paused
        _paused = True
        mouse.paused = True
        keyboard.paused = True
        app_tracker.paused = True

    def _handle_resume(signum, frame):
        global _paused
        _paused = False
        mouse.paused = False
        keyboard.paused = False
        app_tracker.paused = False

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGUSR1, _handle_pause)
    signal.signal(signal.SIGUSR2, _handle_resume)

    # ── Start capture sources ────────────────────────────

    mouse.start(screenshot_callback=screenshot.capture)
    keyboard.start(screenshot_callback=screenshot.capture)
    app_tracker.start()

    print(f"Sifu daemon running (PID {os.getpid()}, session {session_id})")
    sys.stdout.flush()

    # macOS event taps require a CFRunLoop
    from Quartz import CFRunLoopRun

    CFRunLoopRun()


# ── Entry point for subprocess spawning ──────────────────


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m sifu.daemon <session_id>", file=sys.stderr)
        sys.exit(1)
    _run_capture_loop(sys.argv[1])
