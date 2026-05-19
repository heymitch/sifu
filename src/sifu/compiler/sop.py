"""SOP Compiler (Layer 2) — LLM-powered SOP generation from workflow segments."""

import os
import re
import subprocess
import tempfile
from pathlib import Path

from sifu import library
from sifu.compiler.macro import build_macro
from sifu.compiler.meta import build_meta
from sifu.llm import claude_cmd
from sifu.storage.db import get_connection, get_events_by_workflow, DB_PATH


def _open_sops(paths: list):
    """Open compiled SOPs in the configured editor (or system default)."""
    if not paths:
        return
    from sifu.config import load_config
    config = load_config()
    editor = config.get("editor")

    for path in paths:
        if editor:
            subprocess.Popen(["open", "-a", editor, str(path)])
        else:
            # Use system default for .md files
            subprocess.Popen(["open", str(path)])


def _notify(compiled_count: int):
    """Send a macOS notification when compilation finishes."""
    if compiled_count > 0:
        msg = f"{compiled_count} workflow{'s' if compiled_count != 1 else ''} compiled → {library.LIBRARY_DIR}"
    else:
        msg = "No new workflows to compile."
    subprocess.Popen([
        "osascript", "-e",
        f'display notification "{msg}" with title "Sifu"',
    ])


def _get_sops_dir() -> Path:
    """Get configured SOPs directory."""
    from sifu.config import load_config
    config = load_config()
    return Path(config.get("sops_dir", str(Path.home() / ".sifu" / "output" / "sops")))


# ---------------------------------------------------------------------------
# Core compilation — delegates to Claude CLI with file references
# ---------------------------------------------------------------------------


def compile_single(workflow_id: str) -> Path:
    """Compile a workflow into a canonical library unit by delegating to Claude CLI.

    Instead of piping events as text, we tell Claude where the DB is
    and let it query, read screenshots, and write the SOP itself.
    No size limits, no chunking, no stitching.

    Returns the library unit directory Path.
    Raises ValueError if no events exist for the workflow_id.
    Raises RuntimeError if the Claude CLI call fails.
    """
    conn = get_connection()
    events = get_events_by_workflow(conn, workflow_id)
    conn.close()

    if not events:
        raise ValueError(f"No events found for workflow {workflow_id}")

    if not re.match(r'^[\w\-]+$', workflow_id):
        raise ValueError(f"unsafe workflow_id: {workflow_id!r}")

    rows = [dict(e) for e in events]
    screenshots = [r["screenshot_path"] for r in rows if r.get("screenshot_path")]

    screenshots_dir = Path.home() / ".sifu" / "screenshots"
    tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=".md")
    os.close(tmp_fd)
    tmp_md_path = Path(tmp_path_str)

    prompt = f"""Compile workflow "{workflow_id}" into a polished SOP.

DATABASE: {DB_PATH}
Query: SELECT * FROM events WHERE workflow_id = '{workflow_id}' ORDER BY timestamp ASC
This workflow has {len(events)} events.

SCREENSHOTS: {screenshots_dir}
OUTPUT: Write the SOP to {tmp_md_path}

VOICE: Sifu's teacher notebook — sentence case, observational, no marketing words,
no emoji. Open with "I see you do this." style framing. Use mono-style IDs.

INSTRUCTIONS:
1. Read all events for this workflow from the SQLite database
2. Write a markdown SOP: title, time estimate, apps used, numbered steps (what + why)
3. Append a Screenshots section referencing any screenshot_path values: ![capture-N](path)
4. Write the final SOP to the output path; print only DONE"""

    try:
        result = subprocess.run(
            claude_cmd("-p", "--model", "sonnet", "--allowedTools", "Bash,Read,Write,Grep"),
            input=prompt, capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr.strip()}")

        if tmp_md_path.exists() and tmp_md_path.stat().st_size > 0:
            workflow_md = tmp_md_path.read_text(encoding="utf-8")
        else:
            content = result.stdout.strip()
            if content and content != "DONE" and len(content) > 10:
                workflow_md = content
            else:
                raise RuntimeError(f"Claude CLI did not write {tmp_md_path}")
    finally:
        try:
            tmp_md_path.unlink()
        except Exception:
            pass

    macro = build_macro(workflow_id, rows)
    meta = build_meta(workflow_id, rows)
    library.write_unit(
        workflow_id,
        workflow_md=workflow_md,
        macro=macro, meta=meta,
        screenshots=[Path(s) for s in screenshots],
    )
    return library.unit_dir(workflow_id)


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------

def _get_compiled_ids() -> set:
    """Return set of workflow IDs that already have compiled library units."""
    return set(library.list_units())


def _compile_uncompiled(today_only: bool = False) -> None:
    """Find uncompiled workflow segments and compile each one."""
    import click

    try:
        from sifu.patterns.engine import detect_patterns
    except ImportError:
        click.echo("Pattern engine not available yet — no segments to compile.")
        return

    segments = detect_patterns()
    compiled = _get_compiled_ids()

    if not segments:
        click.echo("No workflow segments found.")
        return

    compiled_count = 0
    compiled_paths = []
    for seg in segments:
        wf_id = seg.get("workflow_id")
        if not wf_id:
            continue
        if wf_id in compiled:
            continue
        if today_only:
            from datetime import datetime
            today_str = datetime.now().strftime("%Y-%m-%d")
            if today_str not in seg.get("start_time", ""):
                continue

        # Skip noise: segments that are all window_switch or < 3 meaningful events
        types = seg.get("types", [])
        event_count = seg.get("event_count", 0)
        meaningful_types = [t for t in types if t != "window_switch"]
        if not meaningful_types and event_count > 0:
            click.echo(f"  Skipping {wf_id} (window switches only)")
            continue
        if event_count < 3:
            click.echo(f"  Skipping {wf_id} ({event_count} events — too short)")
            continue

        click.echo(f"  Compiling {wf_id}...")
        try:
            path = compile_single(wf_id)
            click.echo(f"  ✓ {path}")
            compiled_count += 1
            compiled_paths.append(path)
        except Exception as exc:
            click.echo(f"  ✗ {wf_id}: {exc}")

    # Open compiled SOPs in Sublime Text and notify
    _open_sops(compiled_paths)
    _notify(compiled_count)


# ---------------------------------------------------------------------------
# Public CLI-facing functions
# ---------------------------------------------------------------------------

def compile_workflows(workflow=None, today=False, watch=False):
    """Compile workflow segments into SOPs."""
    import click

    click.echo(f"  Workflows will be saved to: {library.LIBRARY_DIR}\n")

    if workflow:
        path = compile_single(workflow)
        click.echo(f"Compiled: {path}")
        return

    if watch:
        import time
        click.echo("Watching for new segments... (Ctrl+C to stop)")
        try:
            while True:
                _compile_uncompiled()
                time.sleep(30)
        except KeyboardInterrupt:
            click.echo("\nStopped watching.")
        return

    # Default: compile all uncompiled segments, optionally filtered to today
    _compile_uncompiled(today_only=today)


def list_sops():
    """List compiled library units."""
    import click

    ids = sorted(library.list_units())
    if not ids:
        click.echo("No workflows compiled yet.")
        return

    click.echo(f"\n  {len(ids)} compiled workflow{'s' if len(ids) != 1 else ''}:\n")
    for wf_id in ids:
        unit = library.read_unit(wf_id)
        title = ""
        if unit:
            for line in unit["workflow_md"].split("\n"):
                if line.startswith("# "):
                    title = line.lstrip("# ").strip()
                    break
        if not title:
            title = wf_id
        click.echo(f"  {wf_id:30s}  {title[:50]}")
