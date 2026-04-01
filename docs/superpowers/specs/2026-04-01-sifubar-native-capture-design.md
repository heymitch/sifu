# SifuBar Native Capture Engine

**Date:** 2026-04-01
**Status:** Approved
**Goal:** Move all macOS capture (CGEventTap, screenshots, app tracking) into the native Swift SifuBar.app so permissions are bound to a stable app identity and persist reliably across reboots, OS updates, and terminal changes.

## Problem

Sifu's Python daemon needs Accessibility and Screen Recording permissions, but macOS binds these to the specific executable that requests them. When the daemon is launched from different terminals (Ghostty, Terminal, SSH), permissions break silently — the daemon runs but captures nothing or only partial data. Non-technical users have no way to diagnose this.

## Solution

SifuBar.app (Swift) becomes the capture engine. It owns all macOS permissions via its bundle identity, captures events directly, writes to SQLite, and manages its own lifecycle (Login Item). The Python CLI becomes a thin client for control commands and stays the engine for analysis (Layers 1-4).

## Architecture

```
SifuBar.app (Swift, always running)
+-- PermissionManager     -> request + verify Accessibility & Screen Recording
+-- CaptureEngine
|   +-- EventTapManager   -> CGEventTap for mouse + keyboard
|   +-- AppTracker        -> NSWorkspace + AXUIElement for app/window tracking
|   +-- ScreenshotCapture -> CGWindowListCreateImage -> JPEG -> disk
|   +-- TextAggregator    -> buffer keystrokes -> flush as text_input events
+-- EventStore            -> SQLite writer (same schema Python reads)
+-- SessionManager        -> create/end sessions, update state file
+-- LoginItemManager      -> SMAppService (auto-start on boot)
+-- CLIBridge             -> watch command file for CLI commands
+-- MenuBarUI             -> existing menu, enhanced with permission status

CLI (Python, on-demand)
+-- sifu start/stop/pause  -> write to ~/.sifu/command.json -> SifuBar executes
+-- sifu compile/coach     -> read from capture.db, run analysis (unchanged)
+-- sifu status/log        -> read from capture.db + daemon.state (unchanged)
```

## 1. Permission Management

### First Launch Flow

1. SifuBar launches -> `PermissionManager` runs preflight
2. Check `AXIsProcessTrusted()` -- if false, show native `NSAlert`:
   - "Sifu needs Accessibility access to track your workflow (clicks, keystrokes, app switches). This stays 100% local."
   - Buttons: [Open System Settings] [Not Now]
3. Check `CGWindowListCreateImage()` test capture -- if returns nil, show second alert:
   - "Sifu needs Screen Recording access to capture screenshots of your workflow."
   - Buttons: [Open System Settings] [Not Now]
4. Poll every 5s until both permissions granted -> start capture automatically
5. Write `~/.sifu/permissions.json` with status + grant timestamps

### Subsequent Launches

- Quick recheck of both permissions on every launch
- If revoked (OS update, re-signing) -> re-prompt immediately
- Menu bar shows degraded state: "Sifu (needs permissions)" until fixed

### Permission Status File

```json
{
  "accessibility": true,
  "screen_recording": true,
  "last_checked": "2026-04-01T14:30:00",
  "granted_at": "2026-04-01T14:25:00"
}
```

## 2. Capture Engine (Swift)

### EventTapManager

Replaces Python `mouse.py` + `keyboard.py`.

- Single CGEventTap mask: `.leftMouseDown`, `.rightMouseDown`, `.keyDown`, `.flagsChanged`, `.scrollWheel`
- Mouse clicks: query `AXUIElementCopyElementAtPosition` for target element role + title
- Keyboard: buffer keystrokes in `TextAggregator` (see below)
- Hotkey detection: Cmd/Ctrl/Option + key -> `shortcut` event type
- Skip `AXSecureTextField` elements (password fields)
- Skip apps in ignore list: 1Password, Bitwarden, KeyChain Access, loginwindow, ScreenSaverEngine

### TextAggregator

Buffers individual keystrokes into coherent text segments.

- Accumulates characters as the user types
- Flush triggers:
  - App switch or window switch
  - 2-second typing pause
  - Enter key pressed
- Terminal apps (Ghostty, iTerm, Terminal, Alacritty, kitty, Warp, Hyper): Enter flushes as `command` event type
- Non-terminal apps: Enter flushes as `text_input` event type
- Backspace removes last character from buffer (not logged as separate event)

### AppTracker

Replaces Python `apps.py`.

- `NSWorkspace.didActivateApplicationNotification` -> `app_switch` events
- Poll active window title via `AXUIElementCopyAttributeValue` every 2s -> `window_switch` on title change
- Record both app name (bundle display name) and window title

### ScreenshotCapture

Replaces Python `screenshots.py`.

- Triggered on: app switch, click event, text flush
- Deduplication: skip if same app + window title within `screenshot_min_interval_s` (from config, default 2.0s)
- Capture: `CGWindowListCreateImage(CGRectInfinite, kCGWindowListOptionOnScreenOnly, kCGNullWindowID, 0)`
- Encode: `NSBitmapImageRep` -> JPEG at `screenshot_quality` (from config, default 80)
- Save to: `~/.sifu/screenshots/YYYY-MM-DD/HH-MM-SS.jpg`
- Disk budget: every 100 captures, check total size against `screenshot_budget_mb` (default 1024), evict oldest

### EventStore (SQLite Writer)

Uses raw `sqlite3` C API (available on macOS without dependencies).

**Schema** (must match Python exactly):

```sql
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
```

**Event types** (string values stored in `type` column):
- `click`, `right_click`, `shortcut`, `text_input`, `command`, `app_switch`, `window_switch`

**Thread safety**: all SQLite writes dispatched to a serial `DispatchQueue`.

**Config**: reads `~/.sifu/config.json` (same file Python's `config.py` uses).

## 3. Session Management

- On capture start: create session row (`session-{uuid8}`, start_time)
- On capture stop: update session end_time
- Update `~/.sifu/daemon.state` (same format as current Python daemon):

```json
{
  "status": "recording",
  "session_id": "session-a1b2c3d4",
  "start_time": "2026-04-01T14:30:00",
  "events": 142,
  "pid": 12345
}
```

- State file is read by CLI and by SifuBar's own menu UI

## 4. CLI Integration

### Command Protocol

`sifu start/stop/pause/resume/sensitive` writes to `~/.sifu/command.json`:

```json
{
  "command": "start",
  "timestamp": "2026-04-01T14:30:00"
}
```

SifuBar polls for this file (during its existing 5s timer). On detection:
1. Parse command
2. Execute (start/stop capture, pause, resume, purge)
3. Delete the command file
4. Update state file

### CLI Flow

1. If SifuBar is running (check `~/.sifu/sifubar.pid`): write command file
2. If SifuBar is not running: `open -a SifuBar`, wait 2s, write command file
3. Analysis commands (`compile`, `coach`, `patterns`, `log`): unchanged -- read from capture.db directly

### Fallback

If SifuBar is genuinely unavailable (headless server, SSH-only):
- CLI prints warning: "SifuBar not available. Capture requires the native app for reliable permissions."
- No silent fallback to broken Python capture

## 5. Login Item

- Register via `SMAppService.mainApp.register()` (macOS 13+)
- Enabled by default on first launch
- Menu toggle: "Start at Login" with checkmark
- Persist preference in `~/.sifu/config.json`: `"start_at_login": true`
- On boot: SifuBar launches -> permission check -> auto-start capture if permissions OK

## 6. Menu Bar UI Changes

### New Permission Status

When permissions missing:
- Title: "Sifu (setup needed)"
- First menu item: "Grant permissions to start recording"
- Click -> runs permission flow (alerts + System Settings)

### New Login Item Toggle

- "Start at Login" menu item with checkmark
- Toggles SMAppService registration

### Existing Menu (unchanged)

All current menu items preserved: start/stop, pause/resume, sensitive, compile, coach, patterns, log, config, open data, quit.

## 7. Python Code Changes

### Removed

- `src/sifu/capture/mouse.py` -- replaced by Swift EventTapManager
- `src/sifu/capture/keyboard.py` -- replaced by Swift EventTapManager
- `src/sifu/capture/apps.py` -- replaced by Swift AppTracker
- `src/sifu/capture/screenshots.py` -- replaced by Swift ScreenshotCapture
- `src/sifu/bar/app.py` -- replaced by native Swift SifuBar
- `_run_capture_loop()` in `daemon.py` -- SifuBar IS the daemon
- `__main__` block in `daemon.py` -- no more subprocess spawning

### Modified

- `daemon.py`:
  - `start_daemon()` -> write `{"command": "start"}` to command file; launch SifuBar if not running
  - `stop_daemon()` -> write `{"command": "stop"}` to command file; keep analysis launch
  - `pause_daemon()` -> write `{"command": "pause"}`
  - `resume_daemon()` -> write `{"command": "resume"}`
  - `toggle_sensitive()` -> write `{"command": "sensitive"}`
  - `get_status()` -> unchanged (reads state file + PID file)
  - Remove `_ensure_swiftbar()`, `_launch_sifubar()`, `_setup_swiftbar()`
  - Remove `_run_capture_loop()` and `__main__` block

### Untouched

- `storage/db.py` -- reads what Swift writes (same schema)
- `storage/disk.py` -- screenshot path helpers still used by Python for reading
- `patterns/engine.py` -- reads from DB
- `compiler/sop.py` -- reads from DB
- `coach/analyzer.py` -- reads from DB
- `automator/generator.py` -- reads from DB
- `config.py` -- shared config (Swift reads same JSON)
- `events.py` -- Event model for Python-side DB reads
- `cli.py` -- calls daemon.py functions (which now delegate)

## 8. Build & Distribution

### Swift Build

- Swift Package Manager (existing `Package.swift`)
- Target: macOS 13+ (already configured)
- Add `Info.plist` with:
  - `NSAccessibilityUsageDescription`
  - `NSScreenCaptureUsageDescription` (if required by macOS for prompt text)
  - `LSUIElement: true` (menu bar only, no dock icon)
  - `CFBundleIdentifier: com.sifu.SifuBar`
- Build: `swift build -c release`
- Install: copy binary to `/usr/local/bin/SifuBar` or create `.app` bundle

### App Bundle Structure

```
SifuBar.app/
  Contents/
    Info.plist
    MacOS/
      SifuBar (executable)
```

Needs to be a proper `.app` bundle for macOS to track permissions by bundle ID.

## 9. Config Keys (read by Swift from ~/.sifu/config.json)

| Key | Type | Default | Used by |
|-----|------|---------|---------|
| screenshot_min_interval_s | float | 2.0 | ScreenshotCapture |
| screenshot_quality | int | 80 | ScreenshotCapture |
| screenshot_budget_mb | int | 1024 | ScreenshotCapture |
| ignore_apps | [string] | ["1Password", "Bitwarden", "KeyChain Access"] | EventTapManager |
| terminal_apps | [string] | ["Terminal", "iTerm2", "Ghostty", ...] | TextAggregator |
| sensitive_purge_minutes | int | 5 | SessionManager |
| start_at_login | bool | true | LoginItemManager |

## 10. File Layout (what ships)

```
extras/SifuBar/
  Package.swift          (updated: add dependencies, Info.plist)
  SifuBar/
    SifuBarApp.swift     (rewritten: full capture engine)
    PermissionManager.swift
    CaptureEngine/
      EventTapManager.swift
      AppTracker.swift
      ScreenshotCapture.swift
      TextAggregator.swift
    Storage/
      EventStore.swift
      SessionManager.swift
    Bridge/
      CLIBridge.swift
      LoginItemManager.swift
    Info.plist
```
