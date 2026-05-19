# Sifu Library v1 — Dev Progress

**Branch:** `feat/library-v1`
**Spec:** `docs/superpowers/specs/2026-05-19-sifu-library-v1-design.md`
**Tagline under test:** *Train Your Replacement.*

Phase-gate reporting per the repo's agentic laws — one update per gate, no batching. Update this file at every gate.

## Status

| Phase | Gate | State |
|---|---|---|
| 0 | Spec approved + branch + design system vendored | ✅ branch `feat/library-v1`, design system at `design-system/`, spec written; awaiting user spec review |
| 1 | Capture: frame-anchored coords + URL via AX (§3) | ✅ frame-anchored coords + URL via AX in SifuBar (Swift); idempotent DB migration; Event model extended |
| 2 | Compiler emits canonical library unit (§1, §4) | ✅ canonical `~/.sifu/library/<id>/` layout (workflow.md / macro.json / meta.json / screenshots); `library.write_unit` sole authoritative writer |
| 3 | Battleship contract doc + thin reference replayer (§2, §9) | ✅ `docs/battleship-contract.md` (schema_version 1, mutation scope, look-ahead symmetry); hardened `validate_macro`; thin `sifu replay --dry-run <id>` |
| 4 | Copy-as-context (`sifu context`) (§6) | ✅ substring matcher emits agent-ready context with NavMacro/Battleship instruction |
| 5 | "Give this to your agent" prompt + bootstrap (§5) | ✅ `src/sifu/install/bootstrap.py` + `give-to-agent.md` + `docs/landing/index.html` marketing-site kit |
| 6 | Library browser styled with Sifu design system (§7) | ✅ `sifu_ui/` package + `sifu ui` command (FastAPI read-only browser, classification-report shape, SSE live-prepend endpoint) |

## Riskiest line

§3b — frame-anchored coordinates. Raw screen (x,y) is what makes coordinate replay brittle and pushes users back to expensive vision loops. If v1 proves only one thing, it proves this. Prioritize the capture-quality tests in Phase 1.

## Roadmap (NOT v1 — see spec §8)

Hosted MCP server (paid cloud sync) · cloud DB + accounts · team/company distribution + hosting license · orchestrator/leaf composition · Tier 3 DOM capture. Do not pull these into v1 plans.

## Log

- **2026-05-19** — Phases 1–6 complete on `feat/library-v1`.
  - Phase 1 (capture): frame-anchored coords + URL via AX in SifuBar (Swift); idempotent DB migration; Event model extended.
  - Phase 2 (compiler): canonical workflow library at `~/.sifu/library/<id>/` (workflow.md / macro.json / meta.json / screenshots); `library.write_unit` is the sole authoritative writer.
  - Phase 3 (contract): `docs/battleship-contract.md` (schema_version 1, mutation scope, look-ahead symmetry); hardened `validate_macro` (ContractError on hostile input); thin reference replayer `sifu replay --dry-run <id>` (test harness only).
  - Phase 4 (consumption): `sifu context <query>` substring matcher emits agent-ready context with NavMacro/Battleship instruction.
  - Phase 5 (install): `src/sifu/install/bootstrap.py` + `give-to-agent.md` + `docs/landing/index.html` on the Sifu marketing-site kit.
  - Phase 6 (ui): `sifu_ui/` package + `sifu ui` command (FastAPI read-only browser on the design system, classification-report shape, SSE live-prepend endpoint).
  - Regression bar held: 7 stale failures (test_capture TestScreenshotDedup ×4 + test_compiler _build_prompt/_add_screenshot_refs ×3) unchanged from Task-0 baseline.
- **2026-05-19** — Brainstorm complete (visual companion). Approach 1 (library-first, lean, copy-as-context, MCP roadmapped) approved. Branch created, Sifu design system vendored to `design-system/`, spec + this doc written. Next: user spec review → writing-plans.
