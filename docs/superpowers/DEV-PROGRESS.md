# Sifu Library v1 — Dev Progress

**Branch:** `feat/library-v1`
**Spec:** `docs/superpowers/specs/2026-05-19-sifu-library-v1-design.md`
**Tagline under test:** *Train Your Replacement.*

Phase-gate reporting per the repo's agentic laws — one update per gate, no batching. Update this file at every gate.

## Status

| Phase | Gate | State |
|---|---|---|
| 0 | Spec approved + branch + design system vendored | ✅ branch `feat/library-v1`, design system at `design-system/`, spec written; awaiting user spec review |
| 1 | Capture: frame-anchored coords + URL via AX (§3) | ⬜ not started |
| 2 | Compiler emits canonical library unit (§1, §4) | ⬜ not started |
| 3 | Battleship contract doc + thin reference replayer (§2, §9) | ⬜ not started |
| 4 | Copy-as-context (`sifu context`) (§6) | ⬜ not started |
| 5 | "Give this to your agent" prompt + bootstrap (§5) | ⬜ not started |
| 6 | Library browser styled with Sifu design system (§7) | ⬜ not started |

## Riskiest line

§3b — frame-anchored coordinates. Raw screen (x,y) is what makes coordinate replay brittle and pushes users back to expensive vision loops. If v1 proves only one thing, it proves this. Prioritize the capture-quality tests in Phase 1.

## Roadmap (NOT v1 — see spec §8)

Hosted MCP server (paid cloud sync) · cloud DB + accounts · team/company distribution + hosting license · orchestrator/leaf composition · Tier 3 DOM capture. Do not pull these into v1 plans.

## Log

- **2026-05-19** — Brainstorm complete (visual companion). Approach 1 (library-first, lean, copy-as-context, MCP roadmapped) approved. Branch created, Sifu design system vendored to `design-system/`, spec + this doc written. Next: user spec review → writing-plans.
