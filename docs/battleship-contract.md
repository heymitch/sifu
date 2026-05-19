# Battleship contract · `macro.json` schema version 1

`macro.json` is the handoff artifact Sifu produces for NavMacro. Sifu writes it; NavMacro reads and runs it. Neither side modifies the other's domain.

**Sifu guarantees the `macro.json` format. NavMacro owns the runtime. Sifu never executes a macro in production.** (The `sifu replay` harness coming in a later task is test-only.)

---

## Source of truth

Emitter: `src/sifu/compiler/macro.py` · `build_macro` · `SCHEMA_VERSION = 1`

Pure and deterministic — rows in, dict out. No I/O, no LLM calls.

---

## Top-level shape

```
{
  "schema_version": 1,
  "workflow_id":   "<string>",
  "steps":         [ <step>, … ]
}
```

| Field | Type | Notes |
|---|---|---|
| `schema_version` | `1` (integer literal) | Always `1` for this version. |
| `workflow_id` | string | Opaque identifier supplied by the caller. Treat it as an opaque string; no format, length bound, or character set is guaranteed — the `wf-…` values in examples are illustrative, not a contract. |
| `steps` | array | Ordered list of step objects, one per recorded event. |

---

## Step shape

Each element of `steps` is an object with the following fields, emitted in this order:

```
{
  "index":      <int>,
  "action":     <"click" | "key" | "type" | "app_switch">,
  "app":        <string | null>,
  "frame":      <frame object | null>,
  "coords":     <coords object | null>,
  "url":        <string | null>,
  "screenshot": <"screenshots/NNN.jpg" | null>,
  "text":       <string | null>,
  "key":        <string | null>,
  "expected":   <expected object | null>
}
```

### `index`

Zero-based integer position of the step in the workflow.

### `action`

Collapsed from the raw `type` field via this mapping (`_ACTION` in `macro.py`):

| Raw event type | `action` value |
|---|---|
| `click` | `click` |
| `right_click` | `click` |
| `shortcut` | `key` |
| `text_input` | `type` |
| `command` | `type` |
| `app_switch` | `app_switch` |
| `window_switch` | `app_switch` |
| *(unknown)* | `click` (default) |

### `app`

Name of the application active at the time of the event, as recorded. `null` when absent from the row.

### `frame`

Window geometry at the time of the event.

```
{
  "display_id":     <int | null>,
  "display_bounds": <[x, y, w, h] | null>,
  "window_rect":    [x, y, w, h],
  "backing_scale":  <float | null>
}
```

`frame` is `null` when `window_rect` is absent or unparseable. When `frame` is non-null, `window_rect` is always a valid four-element array. `display_id`, `display_bounds`, and `backing_scale` may individually be `null` in rows recorded on older versions of the observer.

`display_bounds` and `window_rect` are parsed from JSON strings in the database row (or passed through as lists). An empty string or unparseable value is treated as `null`.

### `coords`

Pixel coordinates of the interaction.

```
{
  "x":      <number>,
  "y":      <number>,
  "rel_to": <"window" | "screen">
}
```

`coords` is `null` when both `position_x` and `position_y` are absent from the row.

`rel_to` is `"window"` when `frame` is non-null, `"screen"` otherwise. NavMacro uses this to resolve the point: window-relative coordinates are offset from `frame.window_rect`; screen-relative coordinates are absolute.

### `url`

URL of the browser page at the time of the event. `null` for non-browser steps. This is a snapshot of state at record time — a guardrail for validation, not a navigation instruction.

### `screenshot`

Path to the screenshot captured at the time of the event, formatted as `screenshots/NNN.jpg` where `NNN` is always exactly 3 digits, zero-padded (e.g. `screenshots/007.jpg`). `null` when no screenshot was recorded.

### `text`

The text typed during a `type` action. `null` for all other action types and when absent from the row. Corresponds to the `text_content` column in the database.

### `key`

The shortcut string for a `key` action (e.g. `"cmd+c"`). `null` for all other action types and when absent. Corresponds to the `shortcut` column.

### `expected`

A post-condition that NavMacro checks after executing the step. Inferred from the **next step's** data, not the current step's.

```
{ "kind": "url",          "value": "<url string>" }
{ "kind": "window_title", "value": "<window name string>" }
```

Priority: if the next step has a `url`, `expected` is `{ "kind": "url", … }`. Otherwise, if the next step has a `window` title, `expected` is `{ "kind": "window_title", … }`. If neither is present, or if there is no next step, `expected` is `null`.

Look-ahead applies uniformly to every step: each step's `expected` is inferred from the immediately following step. Only the final step has no following step and therefore always has `expected: null`. There is no backward or previous-step inference for any step, including step 0.

---

## Failure-loop contract

NavMacro fires `coords` deterministically on each step. After executing a step it compares the observed state against `expected`. On a mismatch it enters vision repair: the vision model identifies the correct target coordinates and **rewrites `coords` in `macro.json` in place**, then execution continues from the corrected position. When NavMacro performs a vision repair, only `coords` is overwritten in `macro.json`; all other fields (`expected`, `screenshot`, `frame`, `url`, `text`, `key`, `action`, `index`) are immutable and must not be rewritten.

Vision is cold-path only. The design rationale: keeping vision out of the happy path preserves context-window budget for the cases that need it. A macro that runs cleanly never touches the vision model.

If vision repair itself fails, the behavior is NavMacro's decision; Sifu does not specify a fallback and does not document one elsewhere.

---

## Annotated example

The following is the real output of `build_macro("wf-demo", rows)` for a two-step browser workflow: a click on a cart page followed by typing a card number on the checkout page.

```json
{
  "schema_version": 1,
  "workflow_id": "wf-demo",
  "steps": [
    {
      "index": 0,
      "action": "click",
      "app": "Google Chrome",
      "frame": {
        "display_id": 1,
        "display_bounds": [0, 0, 1920, 1080],
        "window_rect": [120, 80, 1280, 800],
        "backing_scale": 2.0
      },
      "coords": {
        "x": 840,
        "y": 312,
        "rel_to": "window"
      },
      "url": "https://app.stripe.com/cart",
      "screenshot": "screenshots/000.jpg",
      "text": null,
      "key": null,
      "expected": {
        "kind": "url",
        "value": "https://app.stripe.com/checkout"
      }
    },
    {
      "index": 1,
      "action": "type",
      "app": "Google Chrome",
      "frame": null,
      "coords": null,
      "url": "https://app.stripe.com/checkout",
      "screenshot": null,
      "text": "4242",
      "key": null,
      "expected": null
    }
  ]
}
```

**Step 0 notes:**
- `frame` is present because `window_rect` was recorded. `coords.rel_to` is therefore `"window"`.
- `url` is the cart page — state at record time, not a target to navigate to.
- `expected` looks ahead to step 1's `url` (`https://app.stripe.com/checkout`). NavMacro checks this URL is reached before moving on.
- `screenshot` is `"screenshots/000.jpg"` because a screenshot path was recorded.

**Step 1 notes:**
- Raw type was `text_input`, mapped to `action: "type"`.
- No `window_rect` in the row → `frame` is `null` → `coords` is `null` (no `position_x`/`position_y` either).
- `text` carries the typed content (`"4242"`).
- `expected` is `null` — this is the last step, so there is no next row to look ahead into.
