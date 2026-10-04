# CLAUDE.md — Sifu

Sifu is a local, always-on action logger that turns workflow into SOPs, tutorials, coaching feedback, and automation scripts.

## Architecture

Capture runs in its own process; everything else is the Python core, run on demand.

- **Layer 0: Capture** is a separate process that writes events to SQLite and screenshots to disk. On macOS that is SifuBar.app (Swift, `extras/SifuBar`), using CGEventTap, the Accessibility API and screenshots. <1% CPU. No LLM. No network. The Python core talks to it only through the files in `docs/capture-contract.md`.
- **Layer 1: Pattern Engine** does local workflow segmentation, no LLM.
- **Layer 2: Compiler** is deterministic. It turns a segment into a library unit (`workflow.md`, `macro.json`, `meta.json`, screenshots) under `~/.sifu/library/`. No LLM. The user's own agent does the summarizing after `sifu copy-last`.
- **Layer 3: Coach** reports local efficiency findings, plus optional insights from `claude -p`.
- **Layer 4: Automator** generates scripts via `claude -p`.
- **Classifier** discovers automation capabilities and classifies each workflow step into its optimal method (ELIMINATE, WAIT_FOR, API, CLI, BROWSER, MACRO, MANUAL), with optional `claude -p` refinement.

**Rule**: Layer 0 never calls an LLM. It logs events to SQLite and takes screenshots. That's it. Everything else runs on demand.

## Tech Stack

- Python 3.11+, Click, SQLite for the core and CLI. No pyobjc; it runs on macOS and Linux.
- Swift for SifuBar.app, the menu bar and macOS capture.
- FastAPI and Jinja for the `sifu ui` / `sifu open` library browser (`[ui]` extra).
- Claude CLI for coach insights, the automator and classifier refinement.

## Key Files

- `PRD.md` is the original spec. Its Layers 2-4 predate the deterministic compiler.
- `docs/capture-contract.md` lists the files and SQLite schema shared by capture and core.
- `extras/SifuBar/` is the macOS menu bar app and capture engine (Swift).
- `src/sifu/cli.py` is the CLI entry point.
- `src/sifu/capture/` reaches the capture process (state, commands, the per-platform `CaptureBackend`; `sifubar.py` on macOS).
- `src/sifu/daemon.py` is the CLI side of start/stop/pause/resume/sensitive/status, plus post-stop analysis.
- `src/sifu/events.py` holds the `Event` model and event types.
- `src/sifu/storage/db.py` holds the SQLite schema and queries.
- `src/sifu/patterns/engine.py` segments workflows.
- `src/sifu/compiler/` compiles units (`sop.py`, `render.py`, `macro.py`, `meta.py`, `contract.py`).
- `src/sifu/library.py` reads and writes library units on disk.
- `src/sifu/context_cmd.py` builds the `sifu context` / `sifu copy-last` agent briefing.
- `src/sifu_ui/` is the read-only library browser.
- `src/sifu/coach/analyzer.py` does efficiency coaching.
- `src/sifu/automator/generator.py` generates automation scripts.
- `src/sifu/classifier/` holds `discovery.py`, `classifier.py` and `spec.py`.
- `examples/capabilities.d/` has sample capability descriptors.

## Agentic Engineering Laws

These are non-negotiable for all work in this repo:

1. **1 unit of work = 1 agent. No batching.** One component, one file, one module = one subagent. The #1 failure mode is stuffing too much into one agent window.
2. **Agents write to disk, return one-liners to parent.** Never pass content back through the conversation. Write a file, return the path.
3. **Parent never reads heavy content.** No large files in the main thread. Delegate extraction to subagents.
4. **Haiku for extraction, Sonnet for validation, Opus for orchestration.** Match model cost to task complexity.
5. **Builder writes, Validator checks, only PASS ships.** Every component gets a validation pass before it's considered done.
6. **Build the outer layer BEFORE the inner layer.** Scaffold, CLI skeleton, schema, config, test harness — all before writing features. Agents without specs freestyle. Freestyle agents produce inconsistent output.
7. **Use git worktrees for parallel agent isolation.** Each agent gets its own working copy. No merge conflicts during parallel work.

### Outer Layer → Inner Layer

```
OUTER (first): PRD → scaffold → CLI skeleton → schema → config → test harness
INNER (second): Layer 0 (capture) → Layer 1 (patterns) → Layer 2 (compiler) → Layer 3 (coach) → Layer 4 (automator)
```

## Build Rules

- **Read PRD.md before any build work.** It contains the full spec, file structure, CLI interface, and phased build plan.
- **Outer layer first.** Scaffold, CLI skeleton, schema, config before any feature code.
- **Layer 0 performance is non-negotiable.** If capture adds >1% CPU or >30MB RAM, it ships broken.
- **One component = one agent** when parallelizing builds.
- **Test without a Mac where you can.** `tests/test_capture_contract.py` and `tests/test_capture_control.py` cover the capture boundary on any OS. Checks that need a real Mac go in `tests/test_macos.py`, which skips elsewhere.
- **Pressure test every deliverable** — run it, verify it works. Not "looks right in the file" but "actually runs."
- **After each phase gate**, report what shipped and what's next. Don't batch updates.

## Privacy

- All data local. No network from daemon.
- `sifu sensitive` = pause + purge last 5 min
- Skip AXSecureTextField (password fields)
- Default ignore: 1Password, Bitwarden, KeyChain Access

## Slash Commands

- `/prime` — Initialize a session, read project state, report ready
