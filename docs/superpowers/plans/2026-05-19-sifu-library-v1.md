# Sifu Library v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Sifu so a Mac-captured workflow compiles into one canonical, portable library unit whose `macro.json` is a versioned Battleship/NavMacro contract, handed to the user's own agent via copy-as-context, browsable in a read-only UI styled with the Sifu design system.

**Architecture:** Capture (SifuBar, Swift) gains frame-anchored coordinates + browser URL. The Python compiler emits `~/.sifu/library/<id>/{workflow.md,macro.json,meta.json,screenshots/}` instead of scattered output. A thin reference replayer proves the contract. `sifu context` emits agent-ready context. `sifu ui` serves a read-only browser. MCP server, composition, cloud sync are roadmap — not built here.

**Tech Stack:** Python 3.11+, Click, SQLite (stdlib), pytest; FastAPI + uvicorn + Jinja2 + watchdog (new, UI-only optional extra); Swift (SifuBar, native, manual-verified).

**Spec:** `docs/superpowers/specs/2026-05-19-sifu-library-v1-design.md`
**Branch:** `feat/library-v1` (already created)

---

## File Structure

**Create:**
- `src/sifu/library.py` — library unit paths, write/read of a `~/.sifu/library/<id>/` dir
- `src/sifu/compiler/macro.py` — `macro.json` emitter (pure, deterministic)
- `src/sifu/compiler/meta.py` — `meta.json` emitter (pure, deterministic)
- `src/sifu/compiler/contract.py` — `macro.json` schema validator (`schema_version: 1`)
- `src/sifu/replay.py` — thin reference replayer (test harness, `--dry-run`)
- `src/sifu/context_cmd.py` — workflow matcher + copy-as-context output
- `src/sifu/install/bootstrap.py` — install bootstrap
- `src/sifu/install/give-to-agent.md` — the "Give this to your agent" prompt
- `src/sifu_ui/__init__.py`, `src/sifu_ui/app.py`, `src/sifu_ui/reader.py`, `src/sifu_ui/watcher.py`
- `src/sifu_ui/templates/{base,timeline,doc}.html`
- `src/sifu_ui/static/sifu-design.css` (copied from `design-system/colors_and_type.css`)
- `docs/battleship-contract.md` — versioned macro.json + failure-loop contract
- Tests: `tests/test_library.py`, `tests/test_macro.py`, `tests/test_meta.py`, `tests/test_contract.py`, `tests/test_replay.py`, `tests/test_context.py`, `tests/test_ui_reader.py`

**Modify:**
- `src/sifu/storage/db.py` — add frame/url columns to `SCHEMA`; add `migrate_db()` (ALTER TABLE for existing DBs)
- `src/sifu/events.py` — add frame/url fields to `Event`
- `src/sifu/cli.py` — register `context`, `replay`, `ui` commands; keep `compile` working
- `src/sifu/compiler/sop.py` — `compile_single` writes into a library unit dir
- `extras/SifuBar/SifuBar/Storage/EventStore.swift` — persist frame + url
- `extras/SifuBar/SifuBar/CaptureEngine/EventTapManager.swift` — capture window rect + display + scale
- `extras/SifuBar/SifuBar/CaptureEngine/AppTracker.swift` — read browser URL via AX
- `pyproject.toml` — add `[project.optional-dependencies] ui`; register `sifu` subcommands

---

## Phase 0: Baseline

### Task 0: Establish a green baseline

**Files:** none (verification only)

- [ ] **Step 1: Run the existing suite**

Run: `cd ~/sifu && python -m pytest -q`
Expected: Some tests pass. **Known pre-existing failures**: `tests/test_compiler.py::TestCompiler::test_build_prompt_contains_events` and `test_add_screenshot_refs_*` reference `sifu.compiler.sop._build_prompt` / `_add_screenshot_refs`, which were removed in commit `82e63b2` (compiler now delegates to Claude CLI). These are stale and **out of scope** — do not fix them, do not depend on them. Record the exact set of passing tests as the baseline.

- [ ] **Step 2: Note baseline**

Run: `python -m pytest -q --co | tail -5 && python -m pytest -q 2>&1 | tail -3`
Expected: Capture the pass/fail count. New tasks must not regress any test that passes here.

---

## Phase 1: Frame-anchored capture + browser URL

### Task 1.1: Schema columns + migration for existing DBs

**Files:**
- Modify: `src/sifu/storage/db.py:10-37` (SCHEMA), add `migrate_db`
- Test: `tests/test_library.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_library.py
import sqlite3
from sifu.storage.db import SCHEMA, migrate_db

FRAME_COLS = {"display_id", "display_bounds", "window_rect", "backing_scale", "url"}

def test_schema_has_frame_columns():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    assert FRAME_COLS.issubset(cols)
    conn.close()

def test_migrate_db_adds_columns_to_old_table():
    conn = sqlite3.connect(":memory:")
    # Simulate an OLD events table without frame columns
    conn.executescript("""
        CREATE TABLE events (id INTEGER PRIMARY KEY, timestamp TEXT, type TEXT,
        app TEXT, window TEXT, description TEXT, element TEXT,
        position_x INTEGER, position_y INTEGER, text_content TEXT,
        shortcut TEXT, screenshot_path TEXT, session_id TEXT, workflow_id TEXT);
    """)
    migrate_db(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    assert FRAME_COLS.issubset(cols)
    # Idempotent: running again must not raise
    migrate_db(conn)
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_library.py -q`
Expected: FAIL — `ImportError: cannot import name 'migrate_db'` and frame columns missing.

- [ ] **Step 3: Implement**

In `src/sifu/storage/db.py`, replace the `events` `CREATE TABLE` block in `SCHEMA` so it ends (before `session_id TEXT, workflow_id TEXT`) with the new columns added:

```python
SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,
    app TEXT,
    window TEXT,
    description TEXT,
    element TEXT,
    position_x INTEGER,
    position_y INTEGER,
    text_content TEXT,
    shortcut TEXT,
    screenshot_path TEXT,
    display_id INTEGER,
    display_bounds TEXT,
    window_rect TEXT,
    backing_scale REAL,
    url TEXT,
    session_id TEXT,
    workflow_id TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    start_time TEXT,
    end_time TEXT,
    app_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_app ON events(app);
"""

_FRAME_COLUMNS = [
    ("display_id", "INTEGER"),
    ("display_bounds", "TEXT"),
    ("window_rect", "TEXT"),
    ("backing_scale", "REAL"),
    ("url", "TEXT"),
]


def migrate_db(conn) -> None:
    """Add frame/url columns to a pre-existing events table. Idempotent."""
    existing = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    for name, sqltype in _FRAME_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE events ADD COLUMN {name} {sqltype}")
    conn.commit()
```

Then call `migrate_db(conn)` inside `init_db()` and `get_connection()` right after the connection is obtained (so old DBs upgrade automatically). In `init_db`, after `conn.executescript(SCHEMA)` add `migrate_db(conn)`. In `get_connection`'s non-init branch, after setting `row_factory`, add `migrate_db(conn)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_library.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sifu/storage/db.py tests/test_library.py
git commit -m "feat(capture): frame-anchored + url columns with idempotent migration

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.2: Extend the Event model

**Files:**
- Modify: `src/sifu/events.py:43-57` (Event fields)
- Test: `tests/test_library.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_library.py`:

```python
from sifu.events import Event, EventType

def test_event_roundtrips_frame_fields():
    e = Event(
        type=EventType.CLICK, app="Google Chrome",
        position_x=840, position_y=312,
        display_id=1, display_bounds="[0,0,1920,1080]",
        window_rect="[120,80,1280,800]", backing_scale=2.0,
        url="https://app.stripe.com/cart",
    )
    d = e.to_dict()
    assert d["display_id"] == 1
    assert d["url"] == "https://app.stripe.com/cart"
    e2 = Event.from_dict(d)
    assert e2.backing_scale == 2.0
    assert e2.window_rect == "[120,80,1280,800]"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_library.py::test_event_roundtrips_frame_fields -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'display_id'`.

- [ ] **Step 3: Implement**

In `src/sifu/events.py`, in the `Event` dataclass, add these fields immediately after `screenshot_path`:

```python
    display_id: Optional[int] = None
    display_bounds: Optional[str] = None   # JSON "[x,y,w,h]" of the display
    window_rect: Optional[str] = None      # JSON "[x,y,w,h]" of focused window
    backing_scale: Optional[float] = None  # retina scale factor
    url: Optional[str] = None              # browser address-bar URL (browser apps only)
```

(`to_dict`/`from_dict`/`from_row` need no change — they use `asdict` and `cls(**data)` dynamically.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_library.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sifu/events.py tests/test_library.py
git commit -m "feat(capture): Event carries frame + url fields

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.3: SifuBar — capture window rect, display, scale, browser URL (native)

**Files:**
- Modify: `extras/SifuBar/SifuBar/CaptureEngine/EventTapManager.swift`
- Modify: `extras/SifuBar/SifuBar/CaptureEngine/AppTracker.swift`
- Modify: `extras/SifuBar/SifuBar/Storage/EventStore.swift`

> Native Swift — not pytest-able. This task is **manually verified**. The Python emitter (Phase 2) is written to degrade gracefully when these columns are NULL, so the rest of the plan is testable without this task. Do this task, then verify with the Step below.

- [ ] **Step 1: Add a frame snapshot helper to `EventTapManager.swift`**

Add a static method that returns the focused window rect, active display id + bounds, and backing scale. Place it next to the existing `getWindowTitle()`:

```swift
struct FrameSnapshot {
    let displayID: Int
    let displayBounds: [Int]   // [x,y,w,h]
    let windowRect: [Int]      // [x,y,w,h]
    let backingScale: Double
}

static func getFrameSnapshot() -> FrameSnapshot? {
    guard let app = NSWorkspace.shared.frontmostApplication else { return nil }
    let axApp = AXUIElementCreateApplication(app.processIdentifier)
    var winRef: CFTypeRef?
    AXUIElementCopyAttributeValue(axApp, kAXFocusedWindowAttribute as CFString, &winRef)
    guard let win = winRef else { return nil }
    var posRef: CFTypeRef?
    var sizeRef: CFTypeRef?
    AXUIElementCopyAttributeValue(win as! AXUIElement, kAXPositionAttribute as CFString, &posRef)
    AXUIElementCopyAttributeValue(win as! AXUIElement, kAXSizeAttribute as CFString, &sizeRef)
    var pos = CGPoint.zero
    var size = CGSize.zero
    if let p = posRef { AXValueGetValue(p as! AXValue, .cgPoint, &pos) }
    if let s = sizeRef { AXValueGetValue(s as! AXValue, .cgSize, &size) }
    let winRect = CGRect(origin: pos, size: size)
    let screen = NSScreen.screens.first { $0.frame.intersects(winRect) } ?? NSScreen.main
    guard let scr = screen else { return nil }
    let f = scr.frame
    let did = (scr.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? Int) ?? 0
    return FrameSnapshot(
        displayID: did,
        displayBounds: [Int(f.origin.x), Int(f.origin.y), Int(f.width), Int(f.height)],
        windowRect: [Int(pos.x), Int(pos.y), Int(size.width), Int(size.height)],
        backingScale: Double(scr.backingScaleFactor)
    )
}
```

- [ ] **Step 2: Add a browser-URL reader to `AppTracker.swift`**

Add a static method; only Chrome/Safari/Arc/Edge are read:

```swift
static let browserApps: Set<String> = ["Google Chrome", "Safari", "Arc", "Microsoft Edge", "Brave Browser"]

static func currentBrowserURL(appName: String?) -> String? {
    guard let appName = appName, browserApps.contains(appName) else { return nil }
    guard let app = NSWorkspace.shared.frontmostApplication else { return nil }
    let axApp = AXUIElementCreateApplication(app.processIdentifier)
    var winRef: CFTypeRef?
    AXUIElementCopyAttributeValue(axApp, kAXFocusedWindowAttribute as CFString, &winRef)
    guard let win = winRef else { return nil }
    var urlRef: CFTypeRef?
    let err = AXUIElementCopyAttributeValue(win as! AXUIElement, "AXURL" as CFString, &urlRef)
    if err == .success, let u = urlRef as? NSURL { return u.absoluteString }
    return nil
}
```

- [ ] **Step 3: Persist the new fields in `EventStore.swift`**

In the INSERT statement that writes an event row, add the five columns and bind them: `display_id`, `display_bounds` (JSON string of the array), `window_rect` (JSON string), `backing_scale`, `url`. At the call site that builds an event (where clicks/app-switches are recorded), call `EventTapManager.getFrameSnapshot()` and `AppTracker.currentBrowserURL(appName:)` and pass the values through. Encode arrays with `JSONSerialization` to a compact string (e.g. `[120,80,1280,800]`).

- [ ] **Step 4: Build and manually verify**

Run: `cd ~/sifu/extras/SifuBar && ./build-app.sh`
Then: start capture, click in Chrome on a page, stop, and inspect:
Run: `sqlite3 ~/.sifu/capture.db "SELECT app,position_x,position_y,window_rect,backing_scale,url FROM events WHERE type='click' ORDER BY id DESC LIMIT 3;"`
Expected: recent Chrome click rows show a non-null `window_rect` like `[x,y,w,h]`, `backing_scale` `2.0` (retina), and a `url` starting `http`.

- [ ] **Step 5: Commit**

```bash
git add extras/SifuBar/SifuBar/CaptureEngine/EventTapManager.swift extras/SifuBar/SifuBar/CaptureEngine/AppTracker.swift extras/SifuBar/SifuBar/Storage/EventStore.swift
git commit -m "feat(capture): SifuBar persists frame snapshot + browser URL

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2: Compiler emits the canonical library unit

### Task 2.1: Library unit paths + writer

**Files:**
- Create: `src/sifu/library.py`
- Test: `tests/test_library.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_library.py`:

```python
from pathlib import Path
from sifu import library

def test_unit_dir_and_write(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    u = library.unit_dir("wf-2026-05-19-001")
    assert u == tmp_path / "library" / "wf-2026-05-19-001"
    library.write_unit(
        "wf-2026-05-19-001",
        workflow_md="# I see you do this.\n",
        macro={"schema_version": 1, "workflow_id": "wf-2026-05-19-001", "steps": []},
        meta={"id": "wf-2026-05-19-001", "step_count": 0},
        screenshots=[],
    )
    assert (u / "workflow.md").read_text().startswith("# I see")
    assert '"schema_version": 1' in (u / "macro.json").read_text()
    assert (u / "meta.json").exists()

def test_list_units(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    library.write_unit("wf-a", "# a", {"schema_version":1,"workflow_id":"wf-a","steps":[]}, {"id":"wf-a"}, [])
    library.write_unit("wf-b", "# b", {"schema_version":1,"workflow_id":"wf-b","steps":[]}, {"id":"wf-b"}, [])
    ids = sorted(library.list_units())
    assert ids == ["wf-a", "wf-b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_library.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sifu.library'`.

- [ ] **Step 3: Implement**

```python
# src/sifu/library.py
"""Canonical workflow library — one self-contained dir per workflow."""

import json
import shutil
from pathlib import Path
from typing import Optional

LIBRARY_DIR = Path.home() / ".sifu" / "library"


def unit_dir(workflow_id: str) -> Path:
    return LIBRARY_DIR / workflow_id


def write_unit(workflow_id: str, workflow_md: str, macro: dict,
               meta: dict, screenshots: list[Path]) -> Path:
    """Write a complete library unit. Overwrites an existing unit atomically-ish."""
    d = unit_dir(workflow_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "workflow.md").write_text(workflow_md, encoding="utf-8")
    (d / "macro.json").write_text(json.dumps(macro, indent=2), encoding="utf-8")
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    shots = d / "screenshots"
    shots.mkdir(exist_ok=True)
    for i, src in enumerate(screenshots):
        src = Path(src)
        if src.exists():
            shutil.copy2(src, shots / f"{i:03d}{src.suffix or '.jpg'}")
    return d


def list_units() -> list[str]:
    if not LIBRARY_DIR.exists():
        return []
    return [p.name for p in LIBRARY_DIR.iterdir()
            if p.is_dir() and (p / "macro.json").exists()]


def read_unit(workflow_id: str) -> Optional[dict]:
    d = unit_dir(workflow_id)
    if not (d / "macro.json").exists():
        return None
    return {
        "id": workflow_id,
        "dir": str(d),
        "workflow_md": (d / "workflow.md").read_text(encoding="utf-8") if (d / "workflow.md").exists() else "",
        "macro": json.loads((d / "macro.json").read_text(encoding="utf-8")),
        "meta": json.loads((d / "meta.json").read_text(encoding="utf-8")) if (d / "meta.json").exists() else {},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_library.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sifu/library.py tests/test_library.py
git commit -m "feat(library): canonical workflow unit reader/writer

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.2: `macro.json` emitter (pure, deterministic)

**Files:**
- Create: `src/sifu/compiler/macro.py`
- Test: `tests/test_macro.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_macro.py
from sifu.compiler.macro import build_macro

def _rows():
    # dict rows (sqlite3.Row supports dict()); emitter must accept dicts
    return [
        {"type": "click", "app": "Google Chrome", "position_x": 840, "position_y": 312,
         "display_id": 1, "display_bounds": "[0,0,1920,1080]",
         "window_rect": "[120,80,1280,800]", "backing_scale": 2.0,
         "url": "https://app.stripe.com/cart", "screenshot_path": "/s/4.jpg",
         "text_content": None, "shortcut": None, "window": "Cart"},
        {"type": "text_input", "app": "Google Chrome", "position_x": None, "position_y": None,
         "display_id": None, "display_bounds": None, "window_rect": None, "backing_scale": None,
         "url": "https://app.stripe.com/checkout", "screenshot_path": None,
         "text_content": "gift", "shortcut": None, "window": "Checkout"},
    ]

def test_macro_shape_and_contract():
    m = build_macro("wf-x", _rows())
    assert m["schema_version"] == 1
    assert m["workflow_id"] == "wf-x"
    s0 = m["steps"][0]
    assert s0["action"] == "click"
    assert s0["coords"] == {"x": 840, "y": 312, "rel_to": "window"}
    assert s0["frame"]["window_rect"] == [120, 80, 1280, 800]
    assert s0["frame"]["backing_scale"] == 2.0
    assert s0["url"] == "https://app.stripe.com/cart"
    assert s0["screenshot"] == "screenshots/000.jpg"
    # expected post-condition inferred from NEXT step's url delta
    assert s0["expected"] == {"kind": "url", "value": "https://app.stripe.com/checkout"}

def test_macro_degrades_when_frame_null():
    m = build_macro("wf-y", [{"type": "click", "app": "Notes", "position_x": 10,
        "position_y": 20, "display_id": None, "display_bounds": None,
        "window_rect": None, "backing_scale": None, "url": None,
        "screenshot_path": None, "text_content": None, "shortcut": None, "window": "Notes"}])
    s = m["steps"][0]
    assert s["coords"] == {"x": 10, "y": 20, "rel_to": "screen"}  # falls back to screen
    assert s["frame"] is None
    assert s["expected"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_macro.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sifu.compiler.macro'`.

- [ ] **Step 3: Implement**

```python
# src/sifu/compiler/macro.py
"""macro.json emitter — the Battleship/NavMacro contract (schema_version 1).

Pure and deterministic: rows in, dict out. No I/O, no LLM.
"""

import json
from typing import Optional

SCHEMA_VERSION = 1
_ACTION = {  # event type -> macro action
    "click": "click", "right_click": "click", "shortcut": "key",
    "text_input": "type", "command": "type",
    "app_switch": "app_switch", "window_switch": "app_switch",
}


def _arr(v) -> Optional[list]:
    if v is None or v == "":
        return None
    try:
        return json.loads(v) if isinstance(v, str) else list(v)
    except (ValueError, TypeError):
        return None


def _frame(row) -> Optional[dict]:
    wr = _arr(row.get("window_rect"))
    if wr is None:
        return None
    return {
        "display_id": row.get("display_id"),
        "display_bounds": _arr(row.get("display_bounds")),
        "window_rect": wr,
        "backing_scale": row.get("backing_scale"),
    }


def _expected(next_row) -> Optional[dict]:
    """Infer a post-condition from the NEXT step: prefer a url delta."""
    if next_row is None:
        return None
    url = next_row.get("url")
    if url:
        return {"kind": "url", "value": url}
    win = next_row.get("window")
    if win:
        return {"kind": "window_title", "value": win}
    return None


def build_macro(workflow_id: str, rows: list) -> dict:
    steps = []
    for i, row in enumerate(rows):
        row = dict(row)  # accept sqlite3.Row or dict
        frame = _frame(row)
        px, py = row.get("position_x"), row.get("position_y")
        coords = None
        if px is not None and py is not None:
            coords = {"x": px, "y": py,
                      "rel_to": "window" if frame else "screen"}
        nxt = dict(rows[i + 1]) if i + 1 < len(rows) else None
        steps.append({
            "index": i,
            "action": _ACTION.get(row.get("type"), "click"),
            "app": row.get("app"),
            "frame": frame,
            "coords": coords,
            "url": row.get("url"),
            "screenshot": f"screenshots/{i:03d}.jpg" if row.get("screenshot_path") else None,
            "text": row.get("text_content"),
            "key": row.get("shortcut"),
            "expected": _expected(nxt),
        })
    return {"schema_version": SCHEMA_VERSION, "workflow_id": workflow_id, "steps": steps}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_macro.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sifu/compiler/macro.py tests/test_macro.py
git commit -m "feat(compiler): macro.json emitter (Battleship contract v1)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.3: `meta.json` emitter

**Files:**
- Create: `src/sifu/compiler/meta.py`
- Test: `tests/test_meta.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_meta.py
from sifu.compiler.meta import build_meta

def test_meta():
    rows = [
        {"type":"click","app":"Google Chrome","timestamp":"2026-05-19T10:00:00","session_id":"s1"},
        {"type":"type","app":"Slack","timestamp":"2026-05-19T10:02:30","session_id":"s1"},
    ]
    m = build_meta("wf-2026-05-19-001", rows)
    assert m["id"] == "wf-2026-05-19-001"
    assert m["step_count"] == 2
    assert sorted(m["app_set"]) == ["Google Chrome", "Slack"]
    assert m["captured_at"] == "2026-05-19T10:00:00"
    assert m["source_session"] == "s1"
    assert m["duration_seconds"] == 150
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_meta.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
# src/sifu/compiler/meta.py
"""meta.json emitter — workflow metadata. Pure, deterministic."""

from datetime import datetime


def _parse(ts: str):
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def build_meta(workflow_id: str, rows: list) -> dict:
    rows = [dict(r) for r in rows]
    apps = sorted({r["app"] for r in rows if r.get("app")})
    times = [t for t in (_parse(r.get("timestamp")) for r in rows) if t]
    duration = int((max(times) - min(times)).total_seconds()) if len(times) >= 2 else 0
    sessions = [r.get("session_id") for r in rows if r.get("session_id")]
    return {
        "id": workflow_id,
        "captured_at": rows[0]["timestamp"] if rows and rows[0].get("timestamp") else None,
        "step_count": len(rows),
        "app_set": apps,
        "duration_seconds": duration,
        "source_session": sessions[0] if sessions else None,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_meta.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sifu/compiler/meta.py tests/test_meta.py
git commit -m "feat(compiler): meta.json emitter

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.4: Wire `compile_single` to write a library unit

**Files:**
- Modify: `src/sifu/compiler/sop.py:54-130` (`compile_single`)
- Test: `tests/test_macro.py` (integration via mock)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_macro.py`:

```python
import sqlite3
from unittest.mock import patch, MagicMock
from sifu.events import Event, EventType
from sifu.storage.db import SCHEMA, insert_event
from sifu import library

def test_compile_single_writes_library_unit(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    insert_event(conn, Event(type=EventType.CLICK, app="Google Chrome",
        position_x=10, position_y=20, url="https://x.test",
        workflow_id="wf-int-001", session_id="s1",
        timestamp="2026-05-19T10:00:00"))
    conn.commit()

    with patch("sifu.compiler.sop.get_connection", return_value=conn), \
         patch("subprocess.run") as mrun:
        mrun.return_value = MagicMock(returncode=0, stdout="# I see you do this.\n")
        from sifu.compiler.sop import compile_single
        out = compile_single("wf-int-001")

    assert out == library.unit_dir("wf-int-001")
    assert (out / "macro.json").exists()
    assert (out / "meta.json").exists()
    assert (out / "workflow.md").read_text().startswith("# I see")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_macro.py::test_compile_single_writes_library_unit -q`
Expected: FAIL — `compile_single` returns an SOP `.md` path, not a unit dir; no `macro.json`.

- [ ] **Step 3: Implement**

Rewrite `compile_single` in `src/sifu/compiler/sop.py` to keep the Claude-CLI prose delegation but write into a library unit. Replace the body from `sops_dir = _get_sops_dir()` onward with:

```python
    from sifu import library
    from sifu.compiler.macro import build_macro
    from sifu.compiler.meta import build_meta

    rows = [dict(e) for e in events]
    screenshots = [r["screenshot_path"] for r in rows if r.get("screenshot_path")]

    # Prose: keep the existing Claude-CLI delegation, but target the unit dir.
    unit = library.unit_dir(workflow_id)
    unit.mkdir(parents=True, exist_ok=True)
    md_path = unit / "workflow.md"
    screenshots_dir = Path.home() / ".sifu" / "screenshots"
    prompt = f"""Compile workflow "{workflow_id}" into a polished SOP.

DATABASE: {DB_PATH}
Query: SELECT * FROM events WHERE workflow_id = '{workflow_id}' ORDER BY timestamp ASC
This workflow has {len(events)} events.

SCREENSHOTS: {screenshots_dir}
OUTPUT: Write the SOP to {md_path}

VOICE: Sifu's teacher notebook — sentence case, observational, no marketing words,
no emoji. Open with "I see you do this." style framing. Use mono-style IDs.

INSTRUCTIONS:
1. Read all events for this workflow from the SQLite database
2. Write a markdown SOP: title, time estimate, apps used, numbered steps (what + why)
3. Append a Screenshots section referencing any screenshot_path values: ![capture-N](path)
4. Write the final SOP to the output path; print only DONE"""

    result = subprocess.run(
        claude_cmd("-p", "--model", "sonnet", "--allowedTools", "Bash,Read,Write,Grep"),
        input=prompt, capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI failed: {result.stderr.strip()}")
    if not md_path.exists():
        content = result.stdout.strip()
        if content and content != "DONE" and len(content) > 10:
            md_path.write_text(content, encoding="utf-8")
        else:
            raise RuntimeError(f"Claude CLI did not write {md_path}")

    macro = build_macro(workflow_id, rows)
    meta = build_meta(workflow_id, rows)
    library.write_unit(
        workflow_id,
        workflow_md=md_path.read_text(encoding="utf-8"),
        macro=macro, meta=meta,
        screenshots=[Path(s) for s in screenshots],
    )
    return unit
```

Note: `_get_compiled_ids()` must now detect units. Change it to:

```python
def _get_compiled_ids() -> set:
    from sifu import library
    return set(library.list_units())
```

`list_sops()` and `_compile_uncompiled()` continue to work (the latter calls `compile_single` and uses `_get_compiled_ids`). Update the `list_sops` glob to read units: replace its body with `from sifu import library; ids = sorted(library.list_units())` and print each `id` with its `workflow.md` first `# ` title.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_macro.py -q && python -m pytest -q 2>&1 | tail -2`
Expected: new test PASSES; no regression vs Phase 0 baseline (the stale `test_compiler.py` failures from Task 0 remain, unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/sifu/compiler/sop.py tests/test_macro.py
git commit -m "feat(compiler): compile_single writes canonical library unit

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 3: Battleship contract doc + reference replayer

### Task 3.1: Contract document

**Files:**
- Create: `docs/battleship-contract.md`

- [ ] **Step 1: Write the document**

Create `docs/battleship-contract.md` documenting `macro.json` `schema_version: 1`: every field from `build_macro` (index, action enum `click|key|type|app_switch`, app, frame `{display_id, display_bounds, window_rect, backing_scale}` or null, coords `{x,y,rel_to: window|screen}` or null, url, screenshot, text, key, expected `{kind: url|window_title, value}` or null). Document the failure-loop contract: NavMacro fires `coords` deterministically; after each step it checks `expected`; on mismatch it runs vision repair, **rewrites `coords` in `macro.json`**, and continues; vision is cold-path only. State explicitly: **Sifu guarantees the format; NavMacro owns runtime. Sifu never executes a macro in production** (the `sifu replay` harness in Task 3.3 is test-only).

- [ ] **Step 2: Commit**

```bash
git add docs/battleship-contract.md
git commit -m "docs: macro.json v1 + failure-loop contract

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 3.2: Contract validator

**Files:**
- Create: `src/sifu/compiler/contract.py`
- Test: `tests/test_contract.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_contract.py
import pytest
from sifu.compiler.contract import validate_macro, ContractError

VALID = {"schema_version": 1, "workflow_id": "wf-x", "steps": [
    {"index": 0, "action": "click", "app": "Chrome", "frame": None,
     "coords": {"x": 1, "y": 2, "rel_to": "screen"}, "url": None,
     "screenshot": None, "text": None, "key": None, "expected": None}]}

def test_valid_macro_passes():
    validate_macro(VALID)  # must not raise

def test_bad_schema_version():
    with pytest.raises(ContractError, match="schema_version"):
        validate_macro({**VALID, "schema_version": 2})

def test_bad_action():
    bad = {"schema_version":1,"workflow_id":"w","steps":[{**VALID["steps"][0],"action":"teleport"}]}
    with pytest.raises(ContractError, match="action"):
        validate_macro(bad)

def test_bad_rel_to():
    bad = {"schema_version":1,"workflow_id":"w","steps":[
        {**VALID["steps"][0],"coords":{"x":1,"y":2,"rel_to":"galaxy"}}]}
    with pytest.raises(ContractError, match="rel_to"):
        validate_macro(bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contract.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
# src/sifu/compiler/contract.py
"""Validate a macro dict against the Battleship contract (schema_version 1)."""

SCHEMA_VERSION = 1
_ACTIONS = {"click", "key", "type", "app_switch"}
_REL = {"window", "screen"}
_EXPECTED_KINDS = {"url", "window_title"}


class ContractError(ValueError):
    pass


def validate_macro(m: dict) -> None:
    if m.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"schema_version must be {SCHEMA_VERSION}, got {m.get('schema_version')}")
    if not m.get("workflow_id"):
        raise ContractError("workflow_id is required")
    if not isinstance(m.get("steps"), list):
        raise ContractError("steps must be a list")
    for i, s in enumerate(m["steps"]):
        if s.get("action") not in _ACTIONS:
            raise ContractError(f"step {i}: action {s.get('action')!r} not in {_ACTIONS}")
        c = s.get("coords")
        if c is not None:
            if not {"x", "y", "rel_to"} <= set(c):
                raise ContractError(f"step {i}: coords needs x,y,rel_to")
            if c["rel_to"] not in _REL:
                raise ContractError(f"step {i}: rel_to {c['rel_to']!r} not in {_REL}")
        e = s.get("expected")
        if e is not None and e.get("kind") not in _EXPECTED_KINDS:
            raise ContractError(f"step {i}: expected.kind {e.get('kind')!r} invalid")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_contract.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sifu/compiler/contract.py tests/test_contract.py
git commit -m "feat(compiler): macro.json contract validator

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 3.3: Thin reference replayer (`sifu replay --dry-run`)

**Files:**
- Create: `src/sifu/replay.py`
- Test: `tests/test_replay.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_replay.py
from sifu.replay import dry_run

MACRO = {"schema_version":1,"workflow_id":"wf-x","steps":[
  {"index":0,"action":"click","app":"Chrome","frame":None,
   "coords":{"x":1,"y":2,"rel_to":"screen"},"url":"https://a.test",
   "screenshot":None,"text":None,"key":None,
   "expected":{"kind":"url","value":"https://b.test"}},
  {"index":1,"action":"click","app":"Chrome","frame":None,
   "coords":{"x":3,"y":4,"rel_to":"screen"},"url":"https://b.test",
   "screenshot":None,"text":None,"key":None,"expected":None}]}

def test_dry_run_all_ok():
    # observed states satisfy each step's expected
    report = dry_run(MACRO, observed=["https://b.test", None])
    assert report["ok"] is True
    assert report["failed_step"] is None

def test_dry_run_detects_expected_mismatch():
    report = dry_run(MACRO, observed=["https://WRONG.test", None])
    assert report["ok"] is False
    assert report["failed_step"] == 0
    assert report["reason"].startswith("expected url")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_replay.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
# src/sifu/replay.py
"""Thin reference replayer — TEST HARNESS ONLY.

Proves the Battleship contract: walk steps, after each compare the
observed state against `expected`. Never moves a real mouse. NavMacro
is the real runtime; this must never grow into a competitor.
"""

from sifu.compiler.contract import validate_macro


def dry_run(macro: dict, observed: list) -> dict:
    """`observed[i]` = the state seen AFTER firing step i (url or window
    title), or None if the step has no expected. Returns a report."""
    validate_macro(macro)
    for i, step in enumerate(macro["steps"]):
        exp = step.get("expected")
        if exp is None:
            continue
        seen = observed[i] if i < len(observed) else None
        if seen != exp["value"]:
            return {"ok": False, "failed_step": i,
                    "reason": f"expected {exp['kind']} {exp['value']!r}, saw {seen!r}"}
    return {"ok": True, "failed_step": None, "reason": None}


def replay_cli(workflow_id: str) -> None:
    """`sifu replay --dry-run <id>` — validates a library unit's macro and
    reports its step/expected structure. Does not execute anything."""
    import click
    from sifu import library
    unit = library.read_unit(workflow_id)
    if unit is None:
        click.echo(f"No library unit: {workflow_id}")
        return
    macro = unit["macro"]
    try:
        validate_macro(macro)
    except Exception as exc:
        click.echo(f"✗ contract invalid: {exc}")
        return
    n = len(macro["steps"])
    checks = sum(1 for s in macro["steps"] if s.get("expected"))
    click.echo(f"✓ {workflow_id}: contract valid · {n} steps · {checks} expected post-conditions")
    click.echo("  (dry-run only — NavMacro owns real replay)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_replay.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sifu/replay.py tests/test_replay.py
git commit -m "feat(replay): thin reference replayer proving the contract

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 4: Copy-as-context

### Task 4.1: Workflow matcher + context output

**Files:**
- Create: `src/sifu/context_cmd.py`
- Test: `tests/test_context.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context.py
from sifu import library, context_cmd

def _seed(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    library.write_unit("wf-deploy-001", "# Deploy the site\nPush to Vercel.",
        {"schema_version":1,"workflow_id":"wf-deploy-001","steps":[]},
        {"id":"wf-deploy-001","app_set":["Terminal"]}, [])
    library.write_unit("wf-invoice-001", "# Send an invoice\nOpen Stripe.",
        {"schema_version":1,"workflow_id":"wf-invoice-001","steps":[]},
        {"id":"wf-invoice-001","app_set":["Google Chrome"]}, [])

def test_match_by_title(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    assert context_cmd.best_match("deploy") == "wf-deploy-001"
    assert context_cmd.best_match("invoice stripe") == "wf-invoice-001"
    assert context_cmd.best_match("nonexistent zzz") is None

def test_context_output_has_pointer_and_instruction(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    out = context_cmd.render_context("deploy")
    assert "# Deploy the site" in out
    assert str(library.unit_dir("wf-deploy-001") / "macro.json") in out
    assert "NavMacro" in out and "vision" in out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_context.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
# src/sifu/context_cmd.py
"""Copy-as-context: find the best library workflow, emit agent-ready context.

No index DB (would violate the no-new-DB rule). Substring scoring over
workflow.md + meta is the v1 floor (spec open question 1).
"""

from sifu import library

_INSTRUCTION = (
    "\n\n---\nTo execute this: drive the macro at the path above with the "
    "NavMacro/Battleship skill. Fire coordinates deterministically. Only if a "
    "step's `expected` post-condition fails, fall back to vision to navigate, "
    "then rewrite the macro's coords so the next run is deterministic again.\n"
)


def _score(query: str, text: str) -> int:
    q = query.lower().split()
    t = text.lower()
    return sum(t.count(w) for w in q)


def best_match(query: str):
    best, best_s = None, 0
    for wid in library.list_units():
        u = library.read_unit(wid)
        hay = (u["workflow_md"] + " " + " ".join(u["meta"].get("app_set", [])) + " " + wid)
        s = _score(query, hay)
        if s > best_s:
            best, best_s = wid, s
    return best


def render_context(query: str):
    wid = best_match(query)
    if wid is None:
        return None
    u = library.read_unit(wid)
    macro_path = library.unit_dir(wid) / "macro.json"
    return (f"WORKFLOW · {wid}\n\n{u['workflow_md']}\n\n"
            f"MACRO: {macro_path}{_INSTRUCTION}")


def context_cli(query: str) -> None:
    import click
    out = render_context(query)
    if out is None:
        click.echo(f"No matching workflow for: {query!r}")
        return
    click.echo(out)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_context.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sifu/context_cmd.py tests/test_context.py
git commit -m "feat(context): copy-as-context matcher + output

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 4.2: Register `context` + `replay` CLI commands

**Files:**
- Modify: `src/sifu/cli.py` (add commands near the Review section)
- Test: manual

- [ ] **Step 1: Add commands**

In `src/sifu/cli.py`, after the `show_log` command, add:

```python
@main.command(name="context")
@click.argument("query", nargs=-1, required=True)
def context_cmd_cli(query):
    """Find the best-matching workflow and print it as agent context."""
    from sifu.context_cmd import context_cli
    context_cli(" ".join(query))


@main.command(name="replay")
@click.option("--dry-run", "dry", is_flag=True, default=True,
              help="Validate the macro contract (only mode in v1).")
@click.argument("workflow_id")
def replay_cmd_cli(dry, workflow_id):
    """Dry-run validate a library unit's macro against the contract."""
    from sifu.replay import replay_cli
    replay_cli(workflow_id)
```

- [ ] **Step 2: Verify wiring**

Run: `cd ~/sifu && python -m sifu.cli --help | grep -E "context|replay"`
Expected: both `context` and `replay` listed.

- [ ] **Step 3: Commit**

```bash
git add src/sifu/cli.py
git commit -m "feat(cli): register context + replay commands

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 5: "Give this to your agent" install

### Task 5.1: Bootstrap

**Files:**
- Create: `src/sifu/install/__init__.py` (empty), `src/sifu/install/bootstrap.py`
- Test: `tests/test_context.py` (append — bootstrap dir creation)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_context.py`:

```python
def test_bootstrap_creates_library(tmp_path, monkeypatch):
    from sifu.install import bootstrap
    monkeypatch.setattr(bootstrap.library, "LIBRARY_DIR", tmp_path / "library")
    result = bootstrap.run()
    assert (tmp_path / "library").is_dir()
    assert result["library"] == str(tmp_path / "library")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_context.py::test_bootstrap_creates_library -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
# src/sifu/install/__init__.py
```
```python
# src/sifu/install/bootstrap.py
"""Idempotent local setup the agent runs during install."""

from sifu import library


def run() -> dict:
    library.LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "library": str(library.LIBRARY_DIR),
        "next": "Run `sifu start` to begin capture, then `sifu context <task>`.",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_context.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sifu/install tests/test_context.py
git commit -m "feat(install): idempotent bootstrap

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 5.2: The prompt + landing page

**Files:**
- Create: `src/sifu/install/give-to-agent.md`
- Create: `docs/landing/index.html` (marketing-site kit)

- [ ] **Step 1: Write the prompt**

Create `src/sifu/install/give-to-agent.md` — a paste-into-your-agent prompt instructing the agent to: clone `https://github.com/heymitch/sifu.git ~/sifu`, `pip install -e ~/sifu`, run `python -c "from sifu.install.bootstrap import run; print(run())"`, grant Accessibility permission, then report the printed next step. Sentence case, no emoji, teacher voice (design system rules).

- [ ] **Step 2: Build the landing page from the marketing-site kit**

Create `docs/landing/index.html` recreating `design-system/ui_kits/marketing-site/` (Header, Hero, WhatItDoes, SamplePanel, Pricing, Footer) as a single static HTML file. `<link rel="stylesheet" href="../../design-system/colors_and_type.css">`. The Hero CTA is the "Give this to your agent" prompt in a `<pre>` with a copy button. Enforce hard rules: bone bg, charcoal ink, one indigo accent, stamp red <2%, no shadows/gradients/blur/emoji, mono eyebrow labels, `·` separators, sentence case.

- [ ] **Step 3: Verify no banned patterns**

Run: `cd ~/sifu && grep -nE "box-shadow|linear-gradient|backdrop-filter" docs/landing/index.html design-system/colors_and_type.css || echo "CLEAN"`
Expected: `CLEAN` (no shadows/gradients/blur in our own additions; tokens file already forbids them).

- [ ] **Step 4: Commit**

```bash
git add src/sifu/install/give-to-agent.md docs/landing/index.html
git commit -m "feat(install): give-to-agent prompt + marketing landing page

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 6: Read-only library browser (Sifu design system)

### Task 6.1: UI deps + library reader

**Files:**
- Modify: `pyproject.toml`
- Create: `src/sifu_ui/__init__.py` (empty), `src/sifu_ui/reader.py`
- Test: `tests/test_ui_reader.py`

- [ ] **Step 1: Add the optional extra to `pyproject.toml`**

After the `dependencies` list, add:

```toml
[project.optional-dependencies]
ui = ["fastapi>=0.110", "uvicorn>=0.27", "jinja2>=3.1", "watchdog>=4.0"]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_ui_reader.py
from sifu import library
from sifu_ui import reader

def test_timeline_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    library.write_unit("wf-2026-05-19-001", "# Send an invoice\nbody",
        {"schema_version":1,"workflow_id":"wf-2026-05-19-001","steps":[{"index":0}]},
        {"id":"wf-2026-05-19-001","captured_at":"2026-05-19T10:00:00",
         "app_set":["Google Chrome"],"step_count":1}, [])
    rows = reader.timeline()
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == "wf-2026-05-19-001"
    assert r["title"] == "Send an invoice"
    assert r["captured_at"] == "2026-05-19T10:00:00"
    assert r["step_count"] == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_ui_reader.py -q`
Expected: FAIL — `sifu_ui` missing.

- [ ] **Step 4: Implement**

```python
# src/sifu_ui/__init__.py
```
```python
# src/sifu_ui/reader.py
"""Read-only aggregation over the library for the browser."""

from sifu import library


def _title(md: str, fallback: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line.lstrip("# ").strip()
    return fallback


def timeline() -> list[dict]:
    rows = []
    for wid in library.list_units():
        u = library.read_unit(wid)
        rows.append({
            "id": wid,
            "title": _title(u["workflow_md"], wid),
            "captured_at": u["meta"].get("captured_at"),
            "step_count": u["meta"].get("step_count", len(u["macro"].get("steps", []))),
            "app_set": u["meta"].get("app_set", []),
        })
    return sorted(rows, key=lambda r: r["captured_at"] or "", reverse=True)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_ui_reader.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/sifu_ui/__init__.py src/sifu_ui/reader.py tests/test_ui_reader.py
git commit -m "feat(ui): library reader + ui optional deps

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 6.2: FastAPI app + design-system templates

**Files:**
- Create: `src/sifu_ui/app.py`, `src/sifu_ui/templates/{base,timeline,doc}.html`, `src/sifu_ui/static/sifu-design.css`
- Test: `tests/test_ui_reader.py` (append — TestClient smoke)

- [ ] **Step 1: Copy the design tokens into static**

Run: `cp ~/sifu/design-system/colors_and_type.css ~/sifu/src/sifu_ui/static/sifu-design.css`

- [ ] **Step 2: Write the failing test**

Append to `tests/test_ui_reader.py`:

```python
def test_app_serves_timeline_with_design_system(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    library.write_unit("wf-2026-05-19-001", "# Send an invoice\nbody",
        {"schema_version":1,"workflow_id":"wf-2026-05-19-001","steps":[]},
        {"id":"wf-2026-05-19-001","captured_at":"2026-05-19T10:00:00",
         "app_set":["Chrome"],"step_count":0}, [])
    from fastapi.testclient import TestClient
    from sifu_ui.app import app
    c = TestClient(app)
    html = c.get("/").text
    assert "Send an invoice" in html
    assert "sifu-design.css" in html              # design system loaded
    assert "WORKFLOW ·" in html                    # mono label + brand separator
    for banned in ("box-shadow", "linear-gradient", "backdrop-filter", "😀"):
        assert banned not in html
    assert c.get("/workflow/wf-2026-05-19-001").status_code == 200
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_ui_reader.py::test_app_serves_timeline_with_design_system -q`
Expected: FAIL — `sifu_ui.app` missing.

- [ ] **Step 4: Implement the app + templates**

```python
# src/sifu_ui/app.py
"""Read-only library browser. No claude -p, no editors — copy-as-context
replaces in-app editing (spec §7)."""

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sifu import library
from sifu_ui import reader

_BASE = Path(__file__).parent
app = FastAPI(title="Sifu")
app.mount("/static", StaticFiles(directory=_BASE / "static"), name="static")
templates = Jinja2Templates(directory=str(_BASE / "templates"))


@app.get("/", response_class=HTMLResponse)
def timeline(request: Request):
    return templates.TemplateResponse(
        "timeline.html", {"request": request, "rows": reader.timeline()})


@app.get("/workflow/{workflow_id}", response_class=HTMLResponse)
def workflow(request: Request, workflow_id: str):
    u = library.read_unit(workflow_id)
    if u is None:
        return HTMLResponse("Not found", status_code=404)
    return templates.TemplateResponse(
        "doc.html", {"request": request, "u": u, "wid": workflow_id})
```

`src/sifu_ui/templates/base.html` — bone page, loads `/static/sifu-design.css`, no inline shadows/gradients, mono header wordmark:

```html
<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Sifu</title><link rel="stylesheet" href="/static/sifu-design.css">
<style>body{margin:0;padding:var(--sp-8)}main{max-width:var(--max-w-content);margin:0 auto}
.unit{border:1px solid var(--rule);padding:var(--sp-5);margin:var(--sp-4) 0;border-radius:var(--r-2)}
a.unit{display:block;text-decoration:none;color:var(--fg-1)}
a.unit:hover{background:var(--hover-tint)}</style></head>
<body><main>
<div class="eyebrow">Sifu · workflow library</div>
{% block content %}{% endblock %}
</main></body></html>
```

`src/sifu_ui/templates/timeline.html`:

```html
{% extends "base.html" %}{% block content %}
<h2>Workflows Sifu has classified</h2>
{% for r in rows %}
<a class="unit" href="/workflow/{{ r.id }}">
  <div class="eyebrow">WORKFLOW · {{ r.id }}</div>
  <h4>{{ r.title }}</h4>
  <small>{{ r.captured_at or "—" }} · {{ r.step_count }} steps · {{ r.app_set|join(" · ") }}</small>
</a>
{% else %}<p>No workflows yet. Run <code>sifu start</code>.</p>{% endfor %}
{% endblock %}
```

`src/sifu_ui/templates/doc.html` — classification-report layout (ReportHeader → Summary → ClassifiedSteps → Footer seal), workflow.md rendered as preformatted text in v1 (no markdown lib dependency):

```html
{% extends "base.html" %}{% block content %}
<div class="eyebrow">WORKFLOW · {{ wid }}</div>
<span class="stamp">Classified</span>
<pre style="border:1px solid var(--rule);background:var(--bg-deep);padding:var(--sp-5)">{{ u.workflow_md }}</pre>
<div class="eyebrow">Classified steps · {{ u.macro.steps|length }}</div>
<div class="seal">師 · Verified by Sifu</div>
<p><a href="/">← back</a></p>
{% endblock %}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pip install -e ".[ui]" && python -m pytest tests/test_ui_reader.py -q`
Expected: PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git add src/sifu_ui/app.py src/sifu_ui/templates src/sifu_ui/static tests/test_ui_reader.py
git commit -m "feat(ui): FastAPI read-only browser on the Sifu design system

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 6.3: `sifu ui` command + file watcher

**Files:**
- Create: `src/sifu_ui/watcher.py`
- Modify: `src/sifu/cli.py`
- Test: manual

- [ ] **Step 1: Implement the watcher (SSE live-prepend)**

```python
# src/sifu_ui/watcher.py
"""Watch the library dir; expose an SSE stream the timeline subscribes to."""

import asyncio, json
from sifu import library

_subscribers: list[asyncio.Queue] = []


async def event_stream():
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.append(q)
    try:
        while True:
            msg = await q.get()
            yield f"data: {json.dumps(msg)}\n\n"
    finally:
        _subscribers.remove(q)


def notify(workflow_id: str):
    for q in list(_subscribers):
        q.put_nowait({"type": "new", "id": workflow_id})
```

Add to `src/sifu_ui/app.py`:

```python
from fastapi.responses import StreamingResponse
from sifu_ui.watcher import event_stream

@app.get("/api/events")
async def events():
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

(Polling-based watchdog wiring is optional polish; the SSE endpoint + `notify()` hook satisfy spec §7's live-prepend contract. A `watchdog` Observer calling `notify()` can be added later without interface change.)

- [ ] **Step 2: Add the `ui` command to `src/sifu/cli.py`**

After the `replay` command:

```python
@main.command(name="ui")
@click.option("--port", default=8765, help="Port (default 8765).")
@click.option("--no-open", is_flag=True, help="Do not open a browser.")
def ui_cmd_cli(port, no_open):
    """Start the read-only library browser."""
    import webbrowser, uvicorn
    if not no_open:
        webbrowser.open(f"http://localhost:{port}")
    uvicorn.run("sifu_ui.app:app", host="127.0.0.1", port=port)
```

- [ ] **Step 3: Manually verify**

Run: `cd ~/sifu && sifu ui --no-open --port 8799 &` then `sleep 2 && curl -s localhost:8799/ | grep -c "workflow library"` then `kill %1`
Expected: `1` (page served, design-system eyebrow present).

- [ ] **Step 4: Commit**

```bash
git add src/sifu_ui/watcher.py src/sifu_ui/app.py src/sifu/cli.py
git commit -m "feat(ui): sifu ui command + SSE live-prepend endpoint

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 6.4: Update DEV-PROGRESS + full regression

**Files:**
- Modify: `docs/superpowers/DEV-PROGRESS.md`

- [ ] **Step 1: Full suite**

Run: `cd ~/sifu && python -m pytest -q 2>&1 | tail -3`
Expected: All new tests pass; only the Phase-0 pre-existing `test_compiler.py` stale failures remain (unchanged count).

- [ ] **Step 2: Mark phases done**

Edit the status table in `docs/superpowers/DEV-PROGRESS.md` — set Phases 1–6 to ✅ with one-line gate notes; append a dated Log entry summarizing what shipped.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/DEV-PROGRESS.md
git commit -m "docs(library-v1): phases 1-6 complete

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §1 canonical unit → Task 2.1; §2 macro contract → 2.2 + 3.1 + 3.2; §3a URL / §3b frame coords → 1.1–1.3; §4 compiler refactor → 2.2–2.4; §5 install → 5.1–5.2; §6 copy-as-context → 4.1–4.2; §7 read-only browser + design system → 6.1–6.3; §8 roadmap → not built (verified by acceptance criterion: no MCP/composition/cloud in v1 code — nothing in this plan adds them); §9 testing → tests in every task + 6.4 regression; §10 acceptance → each criterion maps to a task's passing test or manual verify; §11 open questions → resolved inline (substring match 4.1; CLI-only replayer 3.3; expected from next-row delta 2.2/`_expected`). No gaps.
- §2 `expected` inference (next-row url→window_title) implemented in `macro._expected`, asserted in `test_macro_shape_and_contract` and the null-degrade test.

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step shows full code. Doc-only tasks (3.1, 5.2 prompt) specify exact required content and a verification step.

**Type consistency:** `library.LIBRARY_DIR`, `library.unit_dir`, `library.write_unit(workflow_id, workflow_md, macro, meta, screenshots)`, `library.read_unit`, `library.list_units` used identically across Tasks 2.1, 2.4, 3.3, 4.1, 5.1, 6.1. `build_macro(workflow_id, rows)` / `build_meta(workflow_id, rows)` signatures match between definition (2.2/2.3) and call site (2.4). `validate_macro`/`ContractError` consistent across 3.2, 3.3. `reader.timeline()` row keys (`id,title,captured_at,step_count,app_set`) match between 6.1 definition and 6.2 template use. `dry_run(macro, observed)` return keys (`ok,failed_step,reason`) consistent between 3.3 def and test. No drift.

**Note on Phase 0 baseline:** `tests/test_compiler.py` has pre-existing failures (removed `_build_prompt`/`_add_screenshot_refs`). This plan does not touch or depend on them; the regression bar is "no NEW failures vs the Phase-0 recorded count."
