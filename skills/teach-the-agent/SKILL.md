---
name: teach-the-agent
description: Turn a Sifu recording into a reusable agent skill. Use after recording a workflow with Sifu (the staged collection is at ~/.sifu/library/<id>/, or pasted via "Copy Last Workflow"). Decomposes each step into automatable actions vs required knowledge and builds an installable skill that duplicates the workflow.
---

# Teach the Agent

You are turning a workflow the user RECORDED (not one you must replay blindly)
into a reusable, installable agent skill. The staged material is local:

- `~/.sifu/library/<id>/workflow.md` — the human-readable step collection
- `~/.sifu/library/<id>/macro.json` — structured steps (action, app, coords, url, screenshot, expected)
- `~/.sifu/library/<id>/screenshots/` — per-step screenshots

## Method

1. **Read** workflow.md and macro.json. Understand the INTENT, not just the clicks.
2. **Organize** into clean steps; drop one-off session noise that isn't part of the repeatable core.
3. **Decompose each step** into two parts:
   - **Automatable action** — what a tool can do. Prefer a shortcut: a Printing
     Press agent-native CLI for the service, an existing CLI/API, or browser
     automation driven by the step's `url`. Deterministic coords (`macro.json`
     `frame`/`coords`) are next; naive vision-clicking is the last resort.
   - **Required knowledge** — judgment, voice, taste, the "why". Name what's
     missing so the user can supply it.
4. **Compose** by stability/length/frequency: short+stable+frequent → mostly a
   CLI/skill; long+creative+unstable → mostly knowledge + a few automatable
   bookends (and consider a human SOP instead — see the make-human-sop skill).
5. **Build** a SKILL.md with three phases — CONTENT, MISE-EN-PLACE, EXECUTION —
   and gate the irreversible/outward EXECUTION steps. New skills start at
   `notify` (stage + preview, don't fire) and graduate on the user's say-so.

Everything runs on the user's own subscription. Recommend ONE artifact and build it.
