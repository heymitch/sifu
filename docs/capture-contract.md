# Capture contract

Capture runs as its own process. SifuBar.app (Swift, `extras/SifuBar`) is the macOS capture process. A Linux daemon would be a second implementation of the same contract. The Python core never captures anything. It reads what the capture process wrote and sends it commands. Everything that crosses that boundary lives in `~/.sifu/` and is described here.

`tests/test_capture_contract.py` checks this file against `sifu/storage/db.py` and `EventStore.swift`. If you change the schema, change all three.

## Files

| Path under `~/.sifu/` | Written by | Read by | Shape |
|---|---|---|---|
| `capture.db` | capture process (events, sessions); core (`workflow_id`) | core | SQLite, schema below |
| `daemon.state` | capture process | core (`sifu status`, start/stop guards) | JSON, below |
| `command.json` | core | capture process, which deletes it before acting | `{"command": "<name>", "timestamp": "<local time>"}` |
| `<backend>.pid` | capture process while running, removed on exit | core (liveness via `kill -0`) | decimal pid. SifuBar uses `sifubar.pid` |
| `screenshots/YYYY-MM-DD/HH-MM-SS-mmm.jpg` | capture process | core (compile copies them into the library) | JPEG |
| `config.json` | core (`sifu config`) | both | JSON object; capture reads the keys below |

## Commands

`command.json` carries one of `start`, `stop`, `pause`, `resume`, `sensitive`. The capture process polls for the file, deletes it, then acts. `sensitive` pauses capture and deletes the last `sensitive_purge_minutes` of events and their screenshots. Unknown commands are ignored.

## daemon.state

```json
{"status": "recording", "session_id": "session-<uuid>", "start_time": "2026-10-03T10:00:00", "events": 42, "pid": 1234}
```

`status` is `recording`, `paused`, or `stopped`. A stopped state may be just `{"status": "stopped"}`.

## Config keys the capture process reads

`ignore_apps` (list of app names; never record events from them), `terminal_apps` (Enter in these apps records a `command` instead of `text_input`), `screenshot_budget_mb`, `screenshot_min_interval_s`, `screenshot_quality`, `screenshot_max_width`, `idle_timeout_s`, `session_gap_s`, `sensitive_purge_minutes`.

## Privacy rules every capture process keeps

- No keystrokes from password fields (macOS: `AXSecureTextField`).
- No events from `ignore_apps`. The default list includes 1Password, Bitwarden and KeyChain Access.
- No network.

## Schema

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
```

Older databases may lack `display_id`, `display_bounds`, `window_rect`, `backing_scale` and `url`. Both writers add missing columns with `ALTER TABLE ... ADD COLUMN` on open.

## Column meanings

| Column | Meaning |
|---|---|
| `timestamp` | Local wall-clock time, `YYYY-MM-DDTHH:MM:SS`, no zone. The pattern engine compares these as strings. |
| `type` | One of `click`, `right_click`, `shortcut`, `text_input`, `command`, `app_switch`, `window_switch` (`sifu.events.EventType`). |
| `app` | Focused application name. |
| `window` | Focused window title. |
| `description` | One-line summary. SifuBar writes `Clicked 'Save' in Mail`, `Clicked at (x, y) in Mail`, `Shortcut: Cmd+C`, `Typed: ...`, `Command: ...`, `Switched from A to B`, `Window: <title>`. |
| `element` | Accessibility label of the clicked element, when known. |
| `position_x`, `position_y` | Click point in global screen points. |
| `text_content` | Typed text (`text_input`) or the command line (`command`). |
| `shortcut` | Chord as text, e.g. `Cmd+C`. |
| `screenshot_path` | Absolute path to the screenshot taken for this event, or NULL. |
| `display_id` | Platform id of the display holding the focused window. |
| `display_bounds`, `window_rect` | JSON `[x, y, w, h]` in global screen points. |
| `backing_scale` | Pixels per point on that display (2.0 on Retina). |
| `url` | Address-bar URL when the app is a browser. |
| `session_id` | `sessions.id` of the recording session, `session-<uuid>`. |
| `workflow_id` | NULL when captured. The pattern engine fills it in. |
| `sessions.start_time`, `end_time` | Same format as `timestamp`. `end_time` is NULL while recording. |
| `sessions.app_summary` | Unused; SifuBar leaves it NULL. |
