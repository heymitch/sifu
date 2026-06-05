---
name: make-human-sop
description: Turn a Sifu recording into a human-readable SOP with annotated screenshots. Use when a workflow is better handed to a PERSON than automated, or when the user asks for a human SOP / standard operating procedure / training doc from a recording. Runs `sifu annotate` to mark each click point, then writes a step-by-step SOP referencing the annotated images.
---

# Make a Human SOP

You are turning a recorded workflow into a clear SOP a HUMAN can follow. The
staged material is local at `~/.sifu/library/<id>/` (workflow.md, macro.json,
screenshots/).

## Method

1. **Annotate the screenshots.** Run:
   ```
   sifu annotate <id>
   ```
   This writes marked-up images to `~/.sifu/library/<id>/annotated/` — a red
   marker at each click point plus a step number badge. Use these, not the raw
   screenshots.
2. **Write the SOP** as numbered steps. For each step give:
   - a plain-language instruction ("In <app>, click <thing>")
   - the annotated screenshot: `![Step N](annotated/00N.jpg)`
   - any decision/judgment a person needs ("only do this if …")
3. **Open with the goal** — what the procedure accomplishes and when to use it.
4. **Keep it skimmable** — one action per step, screenshots inline, no jargon.

Save the SOP as markdown next to the unit (e.g. `~/.sifu/library/<id>/SOP.md`).
This is the human-handoff counterpart to the teach-the-agent skill; offer the
user both when a workflow mixes automatable and judgment-heavy steps.
