# Copy-to-agent contract (DRAFT for review)

> What `sifu context <query>` should emit when the user clicks "copy."
> This is the product's core artifact: the briefing the user's *own* agent
> receives. Sifu spends no inference here — the receiving agent does the work,
> on the user's subscription.
>
> Status: **proposal.** Not yet wired into `src/sifu/context_cmd.py`. The current
> `_INSTRUCTION` block is NavMacro-centric ("drive the macro, fire coordinates")
> — this replaces it with the skill-building knowledge payload.

---

## Structure

The emitted payload has four parts:

1. **Masthead** — what this is + provenance (workflow id, capture date, app set, step count).
2. **The recorded flow** — `workflow.md` prose (human-readable SOP).
3. **The steps + evidence** — machine-readable step list with screenshot links + a pointer to `macro.json`.
4. **What to do with this** — the knowledge payload. Teaches the agent to convert the recording into an installable skill / workflow / orchestrator, with an execution-tool ladder. *This is the part that's missing today.*

---

## Rendered example (using the real `wf-compile-test` unit)

````
SIFU RECORDING · wf-compile-test
Captured 2026-03-31 · 3 steps · Chrome · 8s
─────────────────────────────────────────────

## The recorded flow

# How to: Search Google

## Steps
### 1. Open browser
Navigated to Google.

## The steps, with evidence

| # | action | app    | detail                | screenshot              |
|---|--------|--------|-----------------------|-------------------------|
| 0 | click  | Chrome | (search bar)          | screenshots/000.jpg     |
| 1 | type   | Chrome | "python tutorial"     | screenshots/001.jpg     |
| 2 | key    | Chrome | Return                | —                       |

MACRO (full structured detail, every field per step):
  /Users/heymitch/.sifu/library/wf-compile-test/macro.json
SCREENSHOTS (one per step, referenced above):
  /Users/heymitch/.sifu/library/wf-compile-test/screenshots/

─────────────────────────────────────────────

## What to do with this

You are receiving a workflow the user performed and recorded with Sifu — a
local action-logger. Above is what they did, step by step, with a screenshot
for each step and a structured `macro.json` describing every action.

Your job is NOT to replay this blindly. It is to ANALYZE the recording and help
the user turn it into something reusable. Read the screenshots and macro.json,
understand the intent behind the steps, then OFFER to build one of:

  1. A SKILL — a SKILL.md the user's agent loads on demand to perform this
     workflow on request. Best when the task recurs and benefits from judgment.
  2. A WORKFLOW — a deterministic script/runbook that executes the steps in
     order. Best when the task is mechanical and identical every time.
  3. An ORCHESTRATOR — a skill/workflow plus an installer that wires it into the
     user's agent (drops the SKILL.md, registers any commands, sets up triggers).
     Best when they want it permanently available, not just this once.

Ask the user which they want before building. Default recommendation: a SKILL
unless the steps are purely mechanical.

### Choosing execution tools (most efficient first)

Whatever you build, prefer the most efficient way to perform each step. Naive
computer-use (screenshot → reason → click) is the universal fallback, not the
default. In rough order of efficiency:

  - DIRECT API CALL — if a step's effect is reachable via an API (e.g. the app
    has a REST/CLI interface), call it directly. Fastest, most reliable.
  - BROWSER API — for web steps, drive the page via the browser's automation
    API using the captured `url`, not pixel clicks.
  - NAVMACRO / BATTLESHIP — fire the captured coordinates deterministically.
    Use the `frame` (window rect + display bounds + backing scale) to translate
    coordinates across screen sizes. Fall back to vision only when a step's
    `expected` post-condition fails, then rewrite the coords so the next run is
    deterministic again. (These are efficiency tools — they make computer-use
    cheaper. They are not required to build the skill.)
  - COMPUTER-USE (vision) — the fallback that always works.

### Structure the skill for accountable execution

Split the skill into three phases. The separation is itself the safety
mechanism — it puts a reviewable seam between "everything is prepared" and
"the irreversible thing happened."

  PHASE 1 · CONTENT — generate what's needed (draft, copy, artifact).
  PHASE 2 · MISE-EN-PLACE — stage it into the destination and configure
    everything up to the trigger (broadcast created, body + CTA loaded,
    audience selected) — all of it reversible / pre-flight.
  PHASE 3 · EXECUTION — the irreversible, outward-facing action (send,
    publish, pay, delete, message an audience).

Optimize Phases 1 and 2 aggressively toward agentic execution
(API > MCP > connector > shortcut > vision) — kill human inefficiency in the
prep. Do NOT optimize Phase 3 for speed; optimize it for accountability.

Classify every step by blast radius:
  - REVERSIBLE / private (drafts, local edits, staging) → may run autonomously.
  - IRREVERSIBLE / outward (send to a list, publish, payment, delete, external
    message) → GATED. Bigger blast radius (a 300k-subscriber send) → harder gate.

Trust is EARNED, not granted. A freshly built skill starts at the most
conservative level for its risky steps and graduates only on the user's say-so
after clean runs. Record the level in the skill's frontmatter so it is explicit,
inspectable, and survives across runs:

  accountability:
    riskiest_step: "send broadcast to subscribers"
    blast_radius: high          # high = large outward audience, irreversible
    level: notify               # notify → approve → auto+undo → autonomous
    graduated_runs: 0

  - notify     — stage through Phase 2, STOP, notify the user with a full
                 preview + the exact action you would take. Do not fire.
                 (default for high blast radius)
  - approve    — stage, present, fire only on explicit one-time approval.
  - auto+undo  — fire, but inside a delay/undo window where the platform allows.
  - autonomous — fire without prompting. Only for low blast radius, or after the
                 user explicitly graduates the skill following several clean runs.

Accountability is also a RECORD, not just a gate: after any Phase 3 action, log
what fired (what was sent, to whom, which links, when) so there is an audit
trail to graduate against and to catch a bad send after the fact.

At build time, ASK the user what accountability level they want for the risky
steps rather than assuming. Default conservative.

### Cost

Everything you do here runs on the user's own subscription. Sifu makes no API
calls of its own — it recorded locally and handed you the material. Build the
skill in this session; don't spin up separate metered services.
````

---

## Notes for wiring (later)

- The masthead fields come from `meta.json` (`id`, `captured_at`, `step_count`,
  `app_set`, `duration_seconds`).
- The step table is derivable from `macro.json` steps (`index`, `action`, `app`,
  `text`/`key`, `screenshot`). Build it in `render_context`.
- Screenshot links: surface the per-step `screenshot` paths inline. Today
  `render_context` emits only `workflow_md` + macro path — the table + screenshot
  index is new.
- The "What to do with this" block is static — it replaces `_INSTRUCTION`.
- `give-to-agent.md` (the install prompt) is a *different* artifact and stays as-is.
- Open question: do we embed the macro.json inline (self-contained, no file read)
  or keep it as a path (smaller payload, agent reads the file)? Path is cleaner
  while everything is local; inline matters if copy ever crosses machines.
