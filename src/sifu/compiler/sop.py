"""SOP Compiler (Layer 2) — LLM-powered SOP generation from workflow segments."""

import subprocess
from pathlib import Path


def _get_sops_dir() -> Path:
    """Get configured SOPs directory."""
    from sifu.config import load_config
    config = load_config()
    return Path(config.get("sops_dir", str(Path.home() / ".sifu" / "output" / "sops")))


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(events) -> str:
    """Build a Claude prompt from a list of raw event rows."""
    lines = [
        "You are converting raw action logs into a clear, step-by-step SOP (Standard Operating Procedure).",
        "Write a polished markdown SOP from these captured user actions.",
        "Include a descriptive title, time estimate, list of apps used, and numbered steps.",
        "Each step should describe WHAT the user did and WHY (if inferable).",
        "Format: markdown with ## headers for sections and ### for steps.",
        "",
        "Raw action log:",
        "---",
    ]
    for i, e in enumerate(events, 1):
        ts = e["timestamp"][11:19] if e["timestamp"] else "?"
        parts = [f"[{ts}]", e["type"]]
        if e["app"]:
            parts.append(f"in {e['app']}")
        if e["text_content"]:
            parts.append(f": {e['text_content']}")
        elif e["shortcut"]:
            parts.append(f": {e['shortcut']}")
        elif e["description"]:
            parts.append(f": {e['description']}")
        lines.append(f"  {i}. {' '.join(parts)}")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Screenshot reference helper
# ---------------------------------------------------------------------------

def _add_screenshot_refs(sop_content: str, events: list) -> str:
    """Append a Screenshots section to the SOP for any events that have captures."""
    screenshots = [
        (i, e["screenshot_path"])
        for i, e in enumerate(events)
        if e["screenshot_path"]
    ]
    if not screenshots:
        return sop_content

    lines = [sop_content, "", "---", "", "## Screenshots", ""]
    for seq, (idx, path) in enumerate(screenshots, 1):
        lines.append(f"### Capture {seq}")
        lines.append(f"![capture-{seq}]({path})")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core compilation
# ---------------------------------------------------------------------------

def compile_single(workflow_id: str) -> Path:
    """Compile a single workflow segment into an SOP markdown file.

    Returns the path of the written file.
    Raises ValueError if no events exist for the workflow_id.
    Raises RuntimeError if the Claude CLI call fails.
    """
    from sifu.storage.db import get_connection, get_events_by_workflow

    conn = get_connection()
    events = get_events_by_workflow(conn, workflow_id)
    conn.close()

    if not events:
        raise ValueError(f"No events found for workflow {workflow_id}")

    prompt = _build_prompt(events)

    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI failed: {result.stderr.strip()}")

    sop_content = result.stdout.strip()
    sop_content = _add_screenshot_refs(sop_content, events)

    sops_dir = _get_sops_dir()
    sops_dir.mkdir(parents=True, exist_ok=True)
    output_path = sops_dir / f"{workflow_id}.md"
    output_path.write_text(sop_content, encoding="utf-8")

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

        click.echo(f"  Compiling {wf_id}...")
        try:
            path = compile_single(wf_id)
            click.echo(f"  ✓ {path}")
        except Exception as exc:
            click.echo(f"  ✗ {wf_id}: {exc}")


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
