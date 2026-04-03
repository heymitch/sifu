"""SOP Compiler (Layer 2) — LLM-powered SOP generation from workflow segments."""

import subprocess
from pathlib import Path


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
        sops_dir = _get_sops_dir()
        msg = f"{compiled_count} SOP{'s' if compiled_count != 1 else ''} compiled → {sops_dir}"
    else:
        msg = "No new SOPs to compile."
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
    """Compile a workflow into an SOP by delegating to Claude CLI.

    Instead of piping events as text, we tell Claude where the DB is
    and let it query, read screenshots, and write the SOP itself.
    No size limits, no chunking, no stitching.

    Returns the path of the written file.
    Raises ValueError if no events exist for the workflow_id.
    Raises RuntimeError if the Claude CLI call fails.
    """
    from sifu.storage.db import get_connection, get_events_by_workflow, DB_PATH

    conn = get_connection()
    events = get_events_by_workflow(conn, workflow_id)
    conn.close()

    if not events:
        raise ValueError(f"No events found for workflow {workflow_id}")

    sops_dir = _get_sops_dir()
    sops_dir.mkdir(parents=True, exist_ok=True)
    output_path = sops_dir / f"{workflow_id}.md"

    screenshots_dir = Path.home() / ".sifu" / "screenshots"
    event_count = len(events)

    prompt = f"""Compile workflow "{workflow_id}" into a polished SOP.

DATABASE: {DB_PATH}
Query: SELECT * FROM events WHERE workflow_id = '{workflow_id}' ORDER BY timestamp ASC
This workflow has {event_count} events.

SCREENSHOTS: {screenshots_dir}
Events with screenshot_path have captures you can reference.

OUTPUT: Write the SOP to {output_path}

INSTRUCTIONS:
1. Read all events for this workflow from the SQLite database
2. Write a polished markdown SOP with:
   - Descriptive title
   - Time estimate (from first to last event timestamp)
   - Apps used
   - Numbered steps describing WHAT the user did and WHY (if inferable)
   - Group related actions into logical phases if the workflow is long
3. Append a Screenshots section at the bottom referencing any screenshot_path values
   Format: ![capture-N](screenshot_path)
4. Write the final SOP to the output path above
5. Do NOT include insight blocks, commentary, or meta-discussion — just the SOP
6. Print only the word DONE when finished"""

    result = subprocess.run(
        ["claude", "-p", "--model", "sonnet", "--allowedTools", "Bash,Read,Write,Grep"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=600,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI failed: {result.stderr.strip()}")

    # Verify the file was written
    if not output_path.exists():
        # Fallback: Claude might have printed the SOP to stdout instead of writing it
        content = result.stdout.strip()
        if content and content != "DONE" and len(content) > 50:
            output_path.write_text(content, encoding="utf-8")
        else:
            raise RuntimeError(f"Claude CLI did not write output to {output_path}")

    return output_path


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------

def _get_compiled_ids() -> set:
    """Return set of workflow IDs that already have compiled SOPs."""
    sops_dir = _get_sops_dir()
    if not sops_dir.exists():
        return set()
    return {p.stem for p in sops_dir.glob("*.md")}


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

    sops_dir = _get_sops_dir()
    click.echo(f"  SOPs will be saved to: {sops_dir}")
    click.echo(f"  (change with: sifu config sops_dir <path>)\n")

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
    """List generated SOPs."""
    import click

    sops_dir = _get_sops_dir()
    if not sops_dir.exists():
        click.echo("No SOPs compiled yet. Run 'sifu compile' first.")
        return

    sops = sorted(sops_dir.glob("*.md"))
    if not sops:
        click.echo("No SOPs compiled yet.")
        return

    click.echo(f"\n  {len(sops)} compiled SOP{'s' if len(sops) != 1 else ''}:\n")
    for sop in sops:
        title = ""
        for line in sop.read_text(encoding="utf-8").split("\n"):
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                break
        if not title:
            title = sop.stem
        size = sop.stat().st_size
        click.echo(
            f"  {sop.stem:30s}  {title[:50]:50s}  ({size} bytes)"
        )
