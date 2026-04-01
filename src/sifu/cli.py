"""Sifu CLI — your workflow sensei."""

import click


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Sifu — local action logger that turns workflow into SOPs."""


# ── Capture ─────────────────────────────────────────────


@main.command()
def start():
    """Start the capture daemon in the background."""
    from sifu.daemon import start_daemon

    start_daemon()


@main.command()
def stop():
    """Stop the capture daemon and finalize the session."""
    from sifu.daemon import stop_daemon

    stop_daemon()


@main.command()
def pause():
    """Temporarily pause capture."""
    from sifu.daemon import pause_daemon

    pause_daemon()


@main.command()
def resume():
    """Resume paused capture."""
    from sifu.daemon import resume_daemon

    resume_daemon()


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def status(as_json):
    """Show daemon status and current session stats."""
    from sifu.daemon import get_status

    get_status(as_json=as_json)


# ── Review ──────────────────────────────────────────────


@main.command(name="log")
@click.option("--app", help="Filter by application name.")
@click.option("--last", help="Time window (e.g. 1h, 30m).")
@click.option("--limit", default=50, help="Max events to show.")
def show_log(app, last, limit):
    """Show today's action log."""
    from sifu.storage.db import query_events

    query_events(app=app, last=last, limit=limit)


@main.command()
@click.option("--today", is_flag=True, help="Today only.")
@click.option("--app", help="Filter by application.")
def patterns(today, app):
    """Show detected workflow patterns."""
    from sifu.patterns.engine import show_patterns

    show_patterns(today=today, app=app)


@main.command()
def sessions():
    """List work sessions."""
    from sifu.storage.db import list_sessions

    list_sessions()


# ── Compile ─────────────────────────────────────────────


@main.command(name="compile")
@click.option("--workflow", help="Compile a specific workflow ID.")
@click.option("--today", is_flag=True, help="Compile today's segments only.")
@click.option("--watch", is_flag=True, help="Auto-compile as segments complete.")
def compile_cmd(workflow, today, watch):
    """Generate SOPs from workflow segments."""
    from sifu.compiler.sop import compile_workflows

    compile_workflows(workflow=workflow, today=today, watch=watch)


@main.command()
def sops():
    """List generated SOPs."""
    from sifu.compiler.sop import list_sops

    list_sops()


# ── Coach ───────────────────────────────────────────────


@main.command()
@click.option("--today", is_flag=True, help="Today only.")
@click.option("--focus", help="Category: shortcuts, redundant, tools, automation.")
def coach(today, focus):
    """Generate coaching report with efficiency suggestions."""
    from sifu.coach.analyzer import run_coach

    run_coach(today=today, focus=focus)


# ── Automate ────────────────────────────────────────────


@main.command()
@click.option("--generate", "workflow_id", help="Generate script for a workflow.")
@click.option("--run", "automation_name", help="Run a saved automation.")
@click.option("--list", "list_all", is_flag=True, help="List saved automations.")
def automate(workflow_id, automation_name, list_all):
    """Manage automation scripts generated from patterns."""
    from sifu.automator.generator import handle_automate

    handle_automate(
        workflow_id=workflow_id,
        automation_name=automation_name,
        list_all=list_all,
    )


# ── Classify ───────────────────────────────────────────


def _display_capabilities(caps):
    """Display discovered capabilities grouped by type."""
    by_type: dict[str, list] = {}
    for cap in caps:
        by_type.setdefault(cap.type, []).append(cap)

    click.echo(f"\n  Discovered {len(caps)} capabilities:\n")
    for cap_type, type_caps in sorted(by_type.items()):
        names = ", ".join(c.name for c in type_caps)
        click.echo(f"  {cap_type:12s}  {names}")
    click.echo()


def _classify_all(caps, use_llm):
    """Classify all unclassified workflow segments."""
    from sifu.classifier.classifier import classify_workflow
    from sifu.classifier.spec import save_spec
    from sifu.patterns.engine import detect_patterns
    from sifu.config import load_config
    from pathlib import Path

    config = load_config()
    workflows_dir = Path(config.get("workflows_dir", ""))
    existing = {p.stem.replace(".workflow", "") for p in workflows_dir.glob("*.workflow.yaml")} if workflows_dir.exists() else set()

    segments = detect_patterns()
    if not segments:
        click.echo("No workflow segments found. Run 'sifu compile' first.")
        return

    classified = 0
    for seg in segments:
        wf_id = seg.get("workflow_id")
        if not wf_id:
            continue

        slug_id = wf_id.lower().replace("_", "-")
        if slug_id in existing:
            continue

        types = seg.get("types", [])
        meaningful = [t for t in types if t not in ("window_switch", "app_switch")]
        if not meaningful:
            click.echo(f"  Skipping {wf_id} (navigation only)")
            continue
        if seg.get("event_count", 0) < 3:
            click.echo(f"  Skipping {wf_id} (too short)")
            continue

        click.echo(f"  Classifying {wf_id}...")
        try:
            spec = classify_workflow(wf_id, caps, use_llm=use_llm)
            path = save_spec(spec)
            comp = spec.comparison()
            click.echo(f"  ✓ {path.name}: {comp['human_steps']} human steps → {comp['compiled_steps']} compiled")
            classified += 1
        except Exception as exc:
            click.echo(f"  ✗ {wf_id}: {exc}")

    click.echo(f"\n  Classified {classified} workflow(s).")


def _reclassify(spec_path, caps, use_llm):
    """Re-classify an existing workflow spec with current capabilities."""
    from sifu.classifier.classifier import classify_workflow
    from sifu.classifier.spec import load_spec, save_spec

    old_spec = load_spec(spec_path)
    click.echo(f"  Re-classifying {old_spec.source_workflow}...")
    click.echo(f"  Capabilities: {len(caps)} discovered")

    new_spec = classify_workflow(old_spec.source_workflow, caps, use_llm=use_llm)
    path = save_spec(new_spec)

    comp = new_spec.comparison()
    click.echo(f"  ✓ Updated: {path}")
    click.echo(f"  Compiled: {comp['compiled_steps']} steps")


def _show_diff(spec_path, cap_dir):
    """Show what would change if re-classified with current capabilities."""
    from sifu.classifier.discovery import discover_capabilities
    from sifu.classifier.classifier import classify_workflow
    from sifu.classifier.spec import load_spec

    old_spec = load_spec(spec_path)
    caps = discover_capabilities(capabilities_dir=cap_dir if cap_dir.exists() else None)

    new_spec = classify_workflow(old_spec.source_workflow, caps, use_llm=False)

    click.echo(f"\n  Diff: {old_spec.id}\n")

    changes = 0
    max_steps = min(len(old_spec.steps), len(new_spec.steps))
    for i in range(max_steps):
        old_step = old_spec.steps[i]
        new_step = new_spec.steps[i]
        if old_step.method != new_step.method:
            click.echo(f"  Step {old_step.id}: {old_step.method} → {new_step.method}")
            click.echo(f"    {old_step.original}")
            changes += 1

    if len(old_spec.steps) != len(new_spec.steps):
        click.echo(f"  Step count changed: {len(old_spec.steps)} → {len(new_spec.steps)}")
        changes += 1

    if changes == 0:
        click.echo("  No changes detected.")
    else:
        click.echo(f"\n  {changes} change(s) detected.")
        click.echo(f"  Run: sifu classify --reclassify {spec_path}")


@main.command()
@click.option("--all", "classify_all", is_flag=True, help="Classify all unclassified workflows.")
@click.option("--discover", "show_discover", is_flag=True, help="Show discovered capabilities.")
@click.option("--reclassify", "reclassify_path", help="Re-classify an existing workflow spec.")
@click.option("--diff", "diff_path", help="Show changes since last classification.")
@click.option("--no-llm", is_flag=True, help="Skip LLM refinement (Phase 1 only).")
@click.argument("workflow_id", required=False)
def classify(workflow_id, classify_all, show_discover, reclassify_path, diff_path, no_llm):
    """Classify workflow steps into automation methods.

    \b
    sifu classify wf-2026-03-31-001   Classify a single workflow
    sifu classify --all               Classify all unclassified workflows
    sifu classify --discover          Show discovered capabilities
    sifu classify --reclassify <spec> Re-classify with updated capabilities
    sifu classify --diff <spec>       Show what changed since last run
    """
    from pathlib import Path
    from sifu.classifier.discovery import discover_capabilities
    from sifu.classifier.spec import save_spec, load_spec
    from sifu.config import load_config

    config = load_config()
    cap_dir = Path(config.get("capabilities_dir", ""))

    if show_discover:
        caps = discover_capabilities(capabilities_dir=cap_dir if cap_dir.exists() else None)
        _display_capabilities(caps)
        return

    if diff_path:
        _show_diff(Path(diff_path), cap_dir)
        return

    caps = discover_capabilities(capabilities_dir=cap_dir if cap_dir.exists() else None)
    use_llm = not no_llm

    if reclassify_path:
        _reclassify(Path(reclassify_path), caps, use_llm)
        return

    if classify_all:
        _classify_all(caps, use_llm)
        return

    if workflow_id:
        from sifu.classifier.classifier import classify_workflow
        click.echo(f"  Classifying {workflow_id}...")
        click.echo(f"  Capabilities: {len(caps)} discovered")

        spec = classify_workflow(workflow_id, caps, use_llm=use_llm)
        path = save_spec(spec)
        comp = spec.comparison()

        click.echo(f"  ✓ Saved: {path}")
        click.echo(f"  Human: {comp['human_steps']} steps, {comp['human_time']}")
        click.echo(f"  Compiled: {comp['compiled_steps']} steps")
        for method, count in sorted(comp["compiled_methods"].items()):
            click.echo(f"    {method}: {count}")
        return

    click.echo("Usage: sifu classify <workflow-id> or sifu classify --all")
    click.echo("  Run 'sifu classify --discover' to see available capabilities.")


# ── Config ──────────────────────────────────────────────


@main.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
def config(key, value):
    """Show or update configuration.

    \b
    sifu config                  Show all settings
    sifu config <key>            Show one setting
    sifu config <key> <value>    Update a setting
    """
    from sifu.config import handle_config

    handle_config(key=key, value=value)


@main.command()
@click.option("--app", required=True, help="App name to add to ignore list.")
def ignore(app):
    """Add an application to the ignore list."""
    from sifu.config import add_ignore_app

    add_ignore_app(app)


@main.command()
def sensitive():
    """Pause capture and purge the last 5 minutes of data."""
    from sifu.daemon import toggle_sensitive

    toggle_sensitive()
