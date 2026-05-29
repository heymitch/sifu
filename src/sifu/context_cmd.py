"""Copy-as-context: find the best library workflow, emit agent-ready context.

The emitted payload is a self-contained briefing for the user's OWN agent —
the recorded workflow + evidence pointers + Sifu's knowledge on how to turn it
into an installable skill. Sifu makes no inference calls of its own; the
receiving agent does the work, on the user's subscription.

Matching is substring scoring over workflow.md prose + app set + the macro's
typed text + the workflow id (no index DB — the no-new-DB rule). See
docs/copy-to-agent-contract.md for the payload contract.
"""

from sifu import library

# The skill-building knowledge payload — the core of the product. It teaches the
# receiving agent to MANUFACTURE a reusable artifact from the recording, not
# replay it. Kept in sync with docs/copy-to-agent-contract.md.
_PAYLOAD = """\

---

## What to do with this

You're receiving a workflow the user performed and recorded with Sifu. Do NOT
replay it blindly. ANALYZE it (read the steps above; read macro.json and the
screenshots if useful), understand the INTENT, then BUILD the most appropriate
reusable artifact:

  1. SKILL — a SKILL.md the user's agent loads on demand. Best when the task
     recurs and benefits from judgment. (Default unless purely mechanical.)
  2. WORKFLOW — a deterministic script/runbook. Best when mechanical and
     identical every time.
  3. ORCHESTRATOR — a skill/workflow plus an installer that wires it in.

Recommend ONE and build it. Separate the REPEATABLE core from one-off noise
captured in the same session — don't bake session-specific side-tasks into the
artifact.

### Execution tools (most efficient first)
Prefer the most efficient way to perform each step; naive vision-clicking is the
fallback, not the default:
  - DIRECT API / CLI — if the effect is reachable via an API, call it.
  - BROWSER AUTOMATION — for web steps, drive the page via the captured `url`.
  - DETERMINISTIC COORDS — fire the macro's frame-anchored coords (translate via
    each step's `frame`). Fall back to vision only when a step's `expected`
    post-condition fails, then rewrite the coords.
  - COMPUTER-USE VISION — the universal fallback.

### Structure for accountable execution
Split the skill into three phases — the separation is itself the safety
mechanism:
  1. CONTENT — generate what's needed (draft, copy, artifact).
  2. MISE-EN-PLACE — stage it into the destination, configure everything up to
     the trigger (all reversible / pre-flight).
  3. EXECUTION — the irreversible, outward-facing action (send, publish, pay,
     delete, message an audience).

Optimize phases 1-2 aggressively toward agentic execution. Do NOT optimize
phase 3 for speed — optimize it for accountability. Classify each step: a
reversible/private step may run autonomously; an irreversible/outward step is
GATED, and the bigger the blast radius (a large-audience send) the harder the
gate. Trust is EARNED — a new skill starts at `notify` (stage everything, then
notify the user with a full preview and the exact action it WOULD take; do NOT
fire) and graduates notify -> approve -> auto+undo -> autonomous only on the
user's say-so after clean runs. Record the level in the skill's frontmatter, and
log every phase-3 action (what fired, to whom, when) — accountability is a
record, not just a gate. At build time, ASK the user what accountability level
they want for the risky steps. Default conservative.

### Cost
Everything runs on the user's own subscription. Sifu made no API calls of its
own — it recorded locally and handed you the material. Build the artifact in
this session; don't spin up separate metered services.
"""


def _score(query: str, text: str) -> int:
    q = query.lower().split()
    t = text.lower()
    return sum(t.count(w) for w in q)


def _macro_typed_text(macro: dict) -> str:
    """Concatenated typed text from a macro's steps. The workflow.md prose
    doesn't always contain what the user literally typed, so include it in the
    match haystack (e.g. matching 'replay email' to the typed subject line)."""
    return " ".join(s["text"] for s in macro.get("steps", []) if s.get("text"))


def best_match(query: str):
    best, best_s = None, 0
    for wid in library.list_units():
        u = library.read_unit(wid)
        if u is None:
            continue
        hay = (
            u["workflow_md"] + " "
            + " ".join(u["meta"].get("app_set", [])) + " "
            + _macro_typed_text(u.get("macro", {})) + " "
            + wid
        )
        s = _score(query, hay)
        if s > best_s:
            best, best_s = wid, s
    return best


def _masthead(wid: str, meta: dict) -> str:
    bits = []
    if meta.get("captured_at"):
        bits.append(str(meta["captured_at"])[:10])
    if meta.get("step_count") is not None:
        bits.append(f"{meta['step_count']} steps")
    dur = meta.get("duration_seconds")
    if dur:
        bits.append(f"~{round(dur / 60)} min" if dur >= 60 else f"{dur}s")
    if meta.get("app_set"):
        bits.append("apps: " + ", ".join(meta["app_set"]))
    head = f"SIFU RECORDING · {wid}"
    return f"{head}\n{'  ·  '.join(bits)}" if bits else head


def render_context(query: str):
    wid = best_match(query)
    if wid is None:
        return None
    u = library.read_unit(wid)
    if u is None:
        return None
    d = library.unit_dir(wid)
    return (
        f"{_masthead(wid, u.get('meta', {}))}\n\n"
        f"## The recorded flow\n\n{u['workflow_md']}\n\n"
        f"## Evidence (structured detail + per-step screenshots)\n"
        f"MACRO: {d / 'macro.json'}\n"
        f"SCREENSHOTS: {d / 'screenshots'}\n"
        f"{_PAYLOAD}"
    )


def context_cli(query: str) -> None:
    import click
    out = render_context(query)
    if out is None:
        click.echo(f"No matching workflow for: {query!r}")
        return
    click.echo(out)
