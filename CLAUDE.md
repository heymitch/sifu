# CLAUDE.md — Sifu

Sifu is a local, always-on action logger that turns workflow into SOPs, tutorials, coaching feedback, and automation scripts.

## Architecture

5 layers, strictly separated:
- **Layer 0: Capture Daemon** — CGEventTap, Accessibility API, screenshots. <1% CPU. No LLM. No network.
- **Layer 1: Pattern Engine** — local sequence detection, no LLM
- **Layer 2: Compiler** — LLM-powered SOP generation from raw logs
- **Layer 3: Coach** — LLM-powered efficiency analysis + shortcut suggestions
- **Layer 4: Automator** — LLM-powered script generation (dev-browser, computer use, bash, AppleScript)

**Rule**: Layer 0 never calls an LLM. It logs events to SQLite and takes screenshots. That's it. Everything else runs on demand.

## Tech Stack

- Python 3.11+ (pyobjc for macOS APIs)
- SQLite (event storage)
- Click (CLI framework)
- Claude CLI / API (Layers 2-4)

## Key Files

- `PRD.md` — full spec, architecture, build plan, CLI interface
- `src/sifu/daemon.py` — capture daemon (Layer 0)
- `src/sifu/cli.py` — CLI entry point
- `src/sifu/capture/` — mouse, keyboard, app tracking, screenshots
- `src/sifu/storage/db.py` — SQLite operations
- `src/sifu/patterns/engine.py` — workflow segmentation
- `src/sifu/compiler/sop.py` — SOP markdown generation
- `src/sifu/coach/analyzer.py` — efficiency coaching
- `src/sifu/automator/generator.py` — automation script generation

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
- **Test capture independently** — mock CGEventTap for unit tests, real tap for integration.
- **Pressure test every deliverable** — run it, verify it works. Not "looks right in the file" but "actually runs."
- **After each phase gate**, report what shipped and what's next. Don't batch updates.

## Privacy

- All data local. No network from daemon.
- `sifu sensitive` = pause + purge last 5 min
- Skip AXSecureTextField (password fields)
- Default ignore: 1Password, Bitwarden, KeyChain Access

## Slash Commands

- `/prime` — Initialize a session, read project state, report ready
