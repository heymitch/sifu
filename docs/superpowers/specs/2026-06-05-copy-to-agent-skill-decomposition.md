# Sifu Copy-to-Agent: skill decomposition (the moat)

**Date**: 2026-06-05
**Status**: Vision / design (NOT ratified, NOT built)
**Repos**: `/Users/heymitch/sifu` (product), referenced by speakeasy cathedral specs
**Related (cathedral)**: `speakeasy-agent/docs/superpowers/specs/2026-06-04-printing-press-to-sifu-copy-to-agent.md` + `2026-06-05-sifu-printing-press-capture-bridge.md`

## The shift that forces this

`claude -p` (Claude subscription via CLI, headless) is being deprecated for programmatic/subscription-included use. Sifu's compiler (`src/sifu/compiler/sop.py`) currently spends a 600s `claude -p --model sonnet` call at compile time to pre-bake a polished SOP. **Remove it.** Not as a workaround — it's the correct architecture:

- Compile becomes **deterministic + instant**, no LLM, no `claude`/`codex` install required → works for every OSS user, no deprecation exposure, **no codex fallback needed**.
- The summarizing moves to where the user is going anyway: **their own agent**, on paste. Doing it at compile was doing the work in the wrong place, twice.
- It fits the library-first thesis exactly: record → copy → **your agent builds the skill**.

## What compile emits now

**Deterministic structured markdown**, STAGED (raw material for the user's agent, not a finished skill). Plus the existing local artifacts: `macro.json`, `screenshots/`, the events DB. Everything is local so the user's agent can **reference the files directly** as it works.

## The copy prompt (the engine — heavy ON PURPOSE)

This is why it can't be a thin compile-time call: it's a big agentic job that belongs in the user's powerful local agent. Pasted in, the prompt drives the agent to:

1. **Organize** the raw manual workflow into clean steps.
2. **Decompose** each step into: **automatable actions** + **the knowledge the agent needs** to perform it.
   - Maps to execution methods: **Printing Press CLI shortcut** (stable/frequent/has-API) · **CLI commands** · **coaching/knowledge** (docs, judgment) · **computer-use** (unstable/GUI).
3. **Compose** — rewrite the summary into a workflow composition judged by **length, stability, frequency**. This decides the OUTPUT SHAPE/RATIO:
   - tight, stable, frequent workflow → mostly a CLI skill
   - long, creative, unstable workflow (e.g. ghostwriting) → mostly knowledge + a human SOP + a few automatable bookends

### Worked example (ghostwriting)
Manual workflow: draft → upload to LinkedIn → edit → outline. Decomposes into, per step: the automatable part (e.g. "post to LinkedIn" → a CLI/Printing Press shortcut) vs the knowledge part (e.g. "draft"/"edit" → voice, taste, judgment the agent must hold).

## Output modes (all click-to-copy; a slash-command / skill COLLECTION installed in the user's agent)

- **Teach the Agent** (default / the basics) → an agent skill that duplicates the workflow.
- **Make a Human SOP** → a human-readable SOP that **annotates the captured screenshots** for the appropriate steps. The big lift; the differentiator.
- (Extensible: more modes as slash commands.)

These commands READ the local Sifu files (collection md, macro.json, screenshots, events) — they're a reusable skill pack, not one-shot prompts.

## The pitch this unlocks

> "I need to do this task but it's really tough to explain — so I'll just DO it, have Sifu watch, and when it compiles I copy it into my agent and decide whether to hand it off to an agent or create a human SOP."

## Why it's the moat (Mitch, verbatim intent)

Anyone can code a click-logger. The paid value is: **intelligent decomposition** (automatable vs knowledge vs coaching) + **composition judgment** (stability/length/frequency → CLI shortcut vs computer-use vs SOP) + **polished outputs** (agent skill; human SOP with annotated screenshots). That's the differentiation between "anyone coding this" and "why they pay for it as a service."

## Build sequence

1. **De-LLM the compile** (keystone) — `sop.py` stops calling `claude -p`; deterministically assemble structured-markdown collection + keep artifacts local.
2. **Copy payload v1** — the decomposition prompt + local-file pointers (the "Teach the Agent" basic). Makes the copy-to-agent contract real.
3. **Slash-command / skill collection** — installable into the user's agent: `teach-the-agent`, `make-human-sop`, … operating on the local Sifu files.
4. **Human SOP w/ annotated screenshots** (the big-lift differentiator).
5. **Dashboard** — prettify the collection, pretty timestamps (not raw strings), in-site editing of the staged collection.

## Open questions

- **Skill-pack distribution:** how does the user install the slash-command collection into their agent (Claude Code skill pack? one-time `sifu install-skills`?).
- **Screenshot annotation:** agent-generated callout instructions + a deterministic render tool, or a vision model? (Determines cost + quality of the human SOP.)
- **Stability/frequency scoring:** deterministic from Sifu's repeat-detection in the events, or agent-judged in the copy prompt? (Likely both: Sifu pre-computes signals, agent judges.)
- **Optional local "summarize now":** keep an opt-in button for users WITH a local `claude`/`codex` who want polished prose in the dashboard without leaving? Or skip for v1. (Lean skip.)
