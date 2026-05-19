# Sifu Library v1 — Design

**Date:** 2026-05-19
**Status:** Draft (pre-approval)
**Branch:** `feat/library-v1`
**Supersedes (partially):** `2026-05-13-sifu-web-ui-design.md` — its Phase 1 read-only viewer survives; its in-app `claude -p` editing (DiffViewer, accept/reject, action panel) is dropped in favor of copy-as-context.
**Roadmap dependents:** `2026-04-28-sifu-composition.md` (orchestrator/leaf) stays roadmap, not v1.

## Goal

Refactor Sifu from a scattered local-output tool into a coherent, testable product: **Mac-only capture → a canonical workflow library → handed to the user's own agent as context → replayed efficiently by the user's existing Battleship/NavMacro skill.** Open-source and local for power users; cloud hosting + company/multi-seat is the paid tier (roadmap). The tagline is the spine: *Train Your Replacement.*

## Constraints (decided in brainstorm 2026-05-19)

- **Mac-only is fine.** No capture-anywhere ambition. Capture (Layer 0) stays native, dumb, no-LLM, no-network.
- **One product, not two.** Capture feeds the library directly. No capture/library split.
- **Lean and testable now.** MCP server and orchestrator/leaf composition are explicitly roadmapped, not v1 blockers.
- **Licensing boundary.** Open-source, local, single-user = free. Cloud-hosting for others / company / multi-seat = paid. Self-hosting-for-others is the licensed line (n8n model).
- **Battleship is external.** NavMacro/Battleship is the user's existing, separately-shipped computer-use skill. Its value is context-window efficiency (deterministic coordinate macros instead of screenshot→vision→turn loops). Sifu *feeds* it; Sifu does not implement replay.

## Architecture

```
SifuBar.app (Swift, Mac-only) ── capture, unchanged except §3
        │ writes
        ↓
   ~/.sifu/capture.db + screenshots/
        │ sifu compile
        ↓
   ~/.sifu/library/<workflow-id>/        ← canonical unit (§1)
     workflow.md   macro.json   meta.json   screenshots/
        │
        ├── sifu context <query> ──→ user's agent (Claude Code / Codex)  (§6)
        │                              └─ drives macro via NavMacro/Battleship skill
        │                                 (deterministic; vision repair on failure → rewrites macro.json)
        │
        └── sifu ui ──→ read-only library browser (§7)  [Sifu design system]

Landing page ──→ "Give this to your agent" prompt ──→ agent installs Sifu locally  (§5)

ROADMAP (out of v1, §8): hosted MCP server (paid cloud sync) · cloud DB + accounts ·
team/company distribution + hosting license · orchestrator/leaf composition · Tier 3 DOM capture
```

## 1. Canonical Workflow Library

Each workflow is one self-contained, portable directory. This replaces the scattered `output/{coach,patterns,workflows,sops}/` split.

```
~/.sifu/library/<workflow-id>/
  workflow.md      — human SOP, the "Train Your Replacement" prompt (teacher-voice, design-system rendered)
  macro.json       — Battleship/NavMacro contract (§2)
  meta.json        — id, captured_at, app_set[], source_session, durations, step_count
  screenshots/NNN.jpg
```

`<workflow-id>` keeps the existing `wf-YYYY-MM-DD-NNN` scheme. A unit is the atomic thing handed to an agent — no cross-directory timestamp matching at read time.

## 2. The Battleship contract — `macro.json`

The product's load-bearing wall. A **versioned, documented** format NavMacro consumes. `schema_version: 1`.

```jsonc
{
  "schema_version": 1,
  "workflow_id": "wf-2026-05-19-001",
  "steps": [
    {
      "index": 0,
      "action": "click",                // click | type | key | app_switch | nav
      "app": "Google Chrome",
      "frame": {                        // §3 — what makes coords replay-stable
        "display_id": 1,
        "display_bounds": [0,0,1920,1080],
        "window_rect": [120,80,1280,800],
        "backing_scale": 2.0
      },
      "coords": { "x": 840, "y": 312, "rel_to": "window" },
      "url": "https://app.stripe.com/cart",   // browser steps only (§ Tier B)
      "screenshot": "screenshots/004.jpg",
      "text": null,                     // for type steps
      "expected": {                     // post-condition → failure detection
        "kind": "url|window_title",
        "value": "https://app.stripe.com/checkout"
      }
    }
  ]
}
```

**Contract responsibilities:**
- **Sifu guarantees**: every step has a frame-anchored `coords`, a paired `screenshot`, and (for browser steps) a `url`; sequences carry `expected` post-conditions where inferable.
- **NavMacro owns runtime** (out of scope here): deterministic fire → detect failure via `expected` mismatch → vision repair → **rewrite `coords` back into `macro.json`** → next run deterministic again. Vision is strictly the cold-path repair, never the normal path — that is the context-efficiency promise.

A standalone `docs/battleship-contract.md` documents `macro.json` v1 and the failure-loop contract, versioned independently of code.

## 3. Capture changes in SifuBar (two focused units)

- **3a. URL via Accessibility (Tier B).** When the frontmost app is a browser (Chrome/Safari/Arc/Edge), read the address-bar URL via AX and attach to the step. One Swift unit in `CaptureEngine`, one `EventStore` field. URL is a *guardrail/context* layer (disambiguation, hard-fail before firing), not a navigation mechanism.
- **3b. Frame-anchored coordinates.** `EventTapManager` records each click with `display_id`, `display_bounds`, focused `window_rect`, and `backing_scale`. **This is the riskiest, highest-value line in the design** — raw screen (x,y) is exactly what makes coordinate replay brittle and pushes users back to expensive vision loops. If v1 proves only one thing, it proves this.

No other capture changes. Layer 0 stays dumb/local/no-LLM/no-network.

## 4. Compiler refactor

`src/sifu/compiler/` emits the §1 unit instead of separate sop/workflow files:
- Reuse existing `sop.py` prose generation (Claude CLI delegation, per commit `82e63b2`) → `workflow.md`, written in the design system's teacher voice (sentence case, mono labels, `WORKFLOW · NNNN`, `·` separators).
- New `macro.py` emitter: `capture.db` events + §3 frame metadata → `macro.json`. Pure, deterministic, golden-file tested.
- New `meta.py`: emits `meta.json`.
- `patterns/engine.py` segmentation unchanged; it defines workflow boundaries.

## 5. Distribution — "Give this to your agent" prompt

Replaces `git clone + pip install` as the front door. A landing-page-ready prompt + a `bootstrap` the agent runs: clone → `pip install -e .` → create `~/.sifu/library/` → register the copy-as-context command/skill → print next step. Open-source, local, single-user. The prompt **is** the distribution primitive. The landing page uses the **marketing-site** UI kit from the Sifu design system.

## 6. Consumption v1 — copy-as-context

`sifu context <query>` (+ a slash-command/skill form for Claude Code/Codex):
1. Find the best-matching library workflow (title/app/substring match over `meta.json` + `workflow.md`; no index DB — that would violate "no new DB").
2. Emit agent-ready context: `workflow.md` body + an absolute pointer to `macro.json` + a fixed instruction line telling the agent to execute via the NavMacro/Battleship skill with the vision-fallback-and-rewrite loop.

This is the **entire** v1 consumption path. No MCP. No run loop inside Sifu.

## 7. Library browser (trimmed) — `sifu ui`

Reuse only Phase 1 of the `2026-05-13` spec: a localhost read-only browser over `~/.sifu/library/`.
- **Dropped from that spec**: in-app `claude -p`, DiffViewer, accept/reject, ActionPanel, operation store. Superseded by §6.
- **Kept**: timeline/list of library units, doc viewer (renders `workflow.md`), screenshot lightbox, file watcher + SSE live-prepend.
- **Visual contract = the Sifu design system** (vendored at `design-system/`). The doc viewer renders a workflow using the **classification-report** UI kit (`ReportHeader`, `ReportSummary`, `Observations`, `ClassifiedSteps`, `Exceptions`, `AgentPlan`, `ReportFooter`). Import `design-system/colors_and_type.css`. Hard rules enforced: bone background, charcoal ink, single indigo accent, stamp red <2%, no drop shadows, no gradients, no blur, no emoji, mono labels for every ID/timestamp, sentence case, `·` as separator. Stamp red reserved for the verified/classified seal on completed workflows only.

## 8. Roadmap (explicitly NOT v1)

Marked as such in-spec so plans don't pull them in:
- Hosted **MCP server** — paid cloud-sync of captured workflows per account; the canonical multi-environment interface. (User: "roadmap it, I don't know how to build it yet, I want to test this first.")
- Cloud DB + accounts; team/company distribution; the hosting license boundary enforcement.
- Orchestrator/leaf **composition** (`2026-04-28` spec).
- Tier 3 **DOM capture** via browser extension.

## 9. Testing & deliverable

- **Capture-quality**: frame-anchoring unit tests with mocked displays/scale factors; assert `macro.json` coords are window-relative and scale-correct.
- **Compiler**: golden-file tests for `macro.json` and `meta.json` from a fixed `capture.db` fixture.
- **Contract proof**: a *thin reference replayer* (NOT NavMacro — just enough to fire a macro and check `expected`) validates one real recorded browser workflow end-to-end. Proves the §2 contract holds.
- **Copy-as-context**: snapshot test of `sifu context <query>` output.
- **UI**: smoke test that `sifu ui` serves a library unit rendered with the design-system tokens (assert `colors_and_type.css` loaded, no shadow/gradient/emoji in output).
- **Dev-progress**: `docs/superpowers/DEV-PROGRESS.md`, updated at each phase gate per the repo's agentic laws (phase-gate reporting, no batching).

## 10. Acceptance criteria

- [ ] A recorded browser session compiles to `~/.sifu/library/<id>/` with `workflow.md`, `macro.json`, `meta.json`, screenshots.
- [ ] Every `macro.json` step has frame-anchored `coords` (window-relative, scale-correct) and a paired screenshot; browser steps carry a `url`.
- [ ] `macro.json` validates against the documented `schema_version: 1` contract.
- [ ] The thin reference replayer replays one real recorded browser workflow and detects an injected `expected` mismatch.
- [ ] `sifu context "<query>"` returns the matching `workflow.md` + `macro.json` pointer + the NavMacro instruction line.
- [ ] The "Give this to your agent" prompt, pasted into a fresh agent, installs Sifu and creates `~/.sifu/library/`.
- [ ] `sifu ui` serves a read-only library browser styled with the Sifu design system; no shadows/gradients/blur/emoji; mono labels and `·` separators present; classification-report layout used for the doc view.
- [ ] MCP server, composition, cloud sync appear nowhere in v1 code — only in §8 and the dev-progress roadmap section.

## 11. Open questions

1. **Workflow matching for `sifu context`** — substring/app match is the v1 floor. Good enough until the library is large; full-text/embeddings need an index (new DB → roadmap with MCP). Start dumb.
2. **Reference replayer surface** — CLI-only (`sifu replay --dry-run <id>`) is enough to prove the contract. It is a test harness, not a product feature; it must never grow into a NavMacro competitor.
3. **`expected` inference quality** — initial heuristic: next step's URL or window-title delta becomes the prior step's `expected`. If too noisy, fall back to URL-only `expected` on browser steps and leave native steps `expected: null`.
