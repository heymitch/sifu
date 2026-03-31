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
