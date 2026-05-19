"""Thin reference replayer — TEST HARNESS ONLY.

Proves the Battleship contract: walk steps, after each compare the
observed state against `expected`. Never moves a real mouse. NavMacro
is the real runtime; this must never grow into a competitor.
"""

from sifu.compiler.contract import validate_macro, ContractError


def dry_run(macro: dict, observed: list) -> dict:
    """`observed` is POSITIONALLY parallel to `macro["steps"]`: same length,
    same indexing — `observed[i]` is the state seen AFTER firing step i (url
    or window title).  Steps that have no `expected` post-condition have their
    `observed[i]` ignored even if present.  If `observed` is shorter than
    `steps`, missing entries are treated as None (triggering a mismatch for
    any step that *does* have an expected value).  Returns a report dict."""
    validate_macro(macro)
    for i, step in enumerate(macro["steps"]):
        exp = step.get("expected")
        if exp is None:
            continue
        seen = observed[i] if i < len(observed) else None
        if seen != exp["value"]:
            return {"ok": False, "failed_step": i,
                    "reason": f"expected {exp['kind']} {exp['value']!r}, saw {seen!r}"}
    return {"ok": True, "failed_step": None, "reason": None}


def replay_cli(workflow_id: str) -> None:
    """`sifu replay --dry-run <id>` — validates a library unit's macro and
    reports its step/expected structure. Does not execute anything."""
    import click
    from sifu import library
    unit = library.read_unit(workflow_id)
    if unit is None:
        click.echo(f"No library unit: {workflow_id}")
        return
    macro = unit["macro"]
    try:
        validate_macro(macro)
    except ContractError as exc:
        click.echo(f"✗ contract invalid: {exc}")
        return
    n = len(macro["steps"])
    checks = sum(1 for s in macro["steps"] if s.get("expected"))
    click.echo(f"✓ {workflow_id}: contract valid · {n} steps · {checks} expected post-conditions")
    click.echo("  (dry-run only — NavMacro owns real replay)")
