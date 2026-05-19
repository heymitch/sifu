"""Copy-as-context: find the best library workflow, emit agent-ready context.

No index DB (would violate the no-new-DB rule). Substring scoring over
workflow.md + meta is the v1 floor (spec open question 1).
"""

from sifu import library

_INSTRUCTION = (
    "\n\n---\nTo execute this: drive the macro at the path above with the "
    "NavMacro/Battleship skill. Fire coordinates deterministically. Only if a "
    "step's `expected` post-condition fails, fall back to vision to navigate, "
    "then rewrite the macro's coords so the next run is deterministic again.\n"
)


def _score(query: str, text: str) -> int:
    q = query.lower().split()
    t = text.lower()
    return sum(t.count(w) for w in q)


def best_match(query: str):
    best, best_s = None, 0
    for wid in library.list_units():
        u = library.read_unit(wid)
        if u is None:
            continue
        hay = (u["workflow_md"] + " " + " ".join(u["meta"].get("app_set", [])) + " " + wid)
        s = _score(query, hay)
        if s > best_s:
            best, best_s = wid, s
    return best


def render_context(query: str):
    wid = best_match(query)
    if wid is None:
        return None
    u = library.read_unit(wid)
    if u is None:
        return None
    macro_path = library.unit_dir(wid) / "macro.json"
    return (f"WORKFLOW · {wid}\n\n{u['workflow_md']}\n\n"
            f"MACRO: {macro_path}{_INSTRUCTION}")


def context_cli(query: str) -> None:
    import click
    out = render_context(query)
    if out is None:
        click.echo(f"No matching workflow for: {query!r}")
        return
    click.echo(out)
