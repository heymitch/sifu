# Sifu — Product Requirements Document

**Version**: 0.1.0
**Date**: 2026-03-31
**One-liner**: Always-on local action logger that turns your workflow into SOPs, tutorials, and automation scripts.

---

## Vision

Leave Sifu on for a week. At the end, you have:
1. Every workflow you perform documented as a step-by-step SOP
2. Coaching feedback on inefficiencies (right-click copy → "use Cmd+C")
3. Automation scripts for repeatable patterns (browser automation, CLI commands, keyboard macros)

Sifu watches the master work, learns the patterns, then teaches them back — and eventually does them.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Layer 0: CAPTURE DAEMON (always on, <1% CPU)       │
│  CGEventTap → clicks, keys, shortcuts, commands     │
│  Accessibility API → element labels, app context    │
│  Smart screenshots → dedup, compress, disk budget   │
│  Output: action log (SQLite) + screenshots (PNG)    │
└──────────────────────┬──────────────────────────────┘
                       │ raw logs
                       ▼
┌─────────────────────────────────────────────────────┐
│  Layer 1: PATTERN ENGINE (local, periodic)          │
│  Sequence detection → group actions into workflows  │
│  Dedup → collapse repeated patterns                 │
│  Session boundaries → detect task switches          │
│  Output: workflow segments with metadata             │
└──────────────────────┬──────────────────────────────┘
                       │ workflow segments
                       ▼
┌─────────────────────────────────────────────────────┐
│  Layer 2: COMPILER (LLM-powered, on demand)         │
│  Raw segments → polished markdown SOPs              │
│  Screenshot annotation → highlight relevant areas   │
│  Tutorial formatting → PB&J-tested step-by-step     │
│  Output: /output/sops/*.md + annotated screenshots  │
└──────────────────────┬──────────────────────────────┘
                       │ compiled SOPs
                       ▼
┌─────────────────────────────────────────────────────┐
│  Layer 3: COACH (LLM-powered, periodic/on demand)   │
│  Efficiency analysis → shortcut suggestions         │
│  Anti-pattern detection → redundant steps           │
│  Automation candidates → "this is scriptable"       │
│  Tool awareness → dev-browser, computer use, CLI    │
│  Output: coaching report + automation suggestions   │
└──────────────────────┬──────────────────────────────┘
                       │ automation candidates
                       ▼
┌─────────────────────────────────────────────────────┐
│  Layer 4: AUTOMATOR (LLM-powered, user-approved)    │
│  Generate executable scripts from patterns          │
│  Browser workflows → dev-browser/computer use       │
│  CLI workflows → bash scripts                       │
│  App workflows → AppleScript/keyboard macros        │
│  Output: /output/automations/*.sh, *.md, *.py       │
└─────────────────────────────────────────────────────┘
```

### Design Principles

1. **Layer 0 must be invisible.** <1% CPU, <50MB RAM. If the user notices it running, it's too heavy. No network calls. No LLM calls. Pure event logging.
2. **Layers 1-4 run on demand or on schedule.** Never in the hot path of capture. The user triggers compilation when ready, or sets a cron.
3. **Screenshots are the expensive part.** Smart dedup: skip if same app + same window + last screenshot <2s ago. Compress to JPEG for storage, keep PNG only for SOP output. Disk budget: configurable, default 1GB, FIFO eviction.
4. **LLM calls stay local to the machine.** Claude CLI (`claude -p`) or API. Never send screenshots to cloud without explicit consent. Text-only by default for LLM compilation; screenshots processed locally.
5. **Every layer's output is useful independently.** Raw logs are grep-able. Pattern segments are reviewable. SOPs are shareable. Coaching reports are actionable. Automations are runnable.

---

## Layer 0: Capture Daemon

### Events Captured

| Event | Data Captured | Screenshot? |
|-------|---------------|-------------|
| Left click | position, app, window, element label | Yes (after 300ms delay) |
| Right click | position, app, window, element label | Yes |
| Keyboard shortcut | combo (e.g., Cmd+C), app, window | Yes |
| Text input | buffered text (flushed on pause/Enter), app, window | No (screenshot on flush) |
| Terminal command | command text (on Enter), app, shell | Yes (after 500ms for output) |
| App switch | from_app, to_app, timestamp | No |
| Tab/window switch | new window title, app | No |

### What's NOT Captured
- Mouse movement / scroll (noise)
- Passwords in known password fields (accessibility API role check)
- Events in IGNORE_APPS (screensaver, login window)
- Modifier-only keystrokes (bare Shift, bare Cmd)

### Screenshot Strategy

```python
def should_screenshot(event, last_screenshot):
    # Skip if same app + window and <2s since last screenshot
    if (event.app == last_screenshot.app
        and event.window == last_screenshot.window
        and event.time - last_screenshot.time < 2.0):
        return False
    # Skip for text input mid-typing (screenshot on flush only)
    if event.type == "text_input" and not event.flushed:
        return False
    return True
```

### Storage

- **Database**: SQLite at `~/.sifu/capture.db`
- **Screenshots**: `~/.sifu/screenshots/YYYY-MM-DD/HH-MM-SS-NNN.jpg`
- **Disk budget**: Default 1GB. FIFO eviction of oldest screenshots. Logs kept indefinitely (tiny).
- **Schema**:

```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,          -- click, right_click, shortcut, text_input, command, app_switch
    app TEXT,
    window TEXT,
    description TEXT,
    element TEXT,                -- accessibility label
    position_x INTEGER,
    position_y INTEGER,
    text_content TEXT,           -- typed text or command
    shortcut TEXT,               -- Cmd+C, etc.
    screenshot_path TEXT,
    session_id TEXT,             -- groups events by work session
    workflow_id TEXT             -- assigned by pattern engine
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    start_time TEXT,
    end_time TEXT,
    app_summary TEXT             -- JSON: {app: seconds_active}
);
```

### Performance Budget

| Metric | Target |
|--------|--------|
| CPU (idle) | <0.5% |
| CPU (during click) | <2% spike, <100ms |
| RAM | <30MB resident |
| Disk (per hour, active use) | ~20-50MB (mostly screenshots) |
| Screenshot capture time | <200ms |

### Daemon Control

```bash
sifu start              # start capture daemon (background)
sifu stop               # stop daemon, finalize session
sifu status             # running? current session stats
sifu pause              # pause capture (meetings, sensitive work)
sifu resume             # resume capture
```

---

## Layer 1: Pattern Engine

Runs locally, no LLM needed. Groups raw events into workflow segments.

### Segmentation Rules

1. **App switch** with >30s gap = new segment
2. **5+ minute idle** = session boundary
3. **Repeated sequence** (same 3+ actions in same order, same app) = flagged as pattern
4. **Terminal command clusters** = grouped into one segment

### Output

```json
{
  "workflow_id": "wf-2026-03-31-001",
  "title": "auto: Ghostty → git status → edit → commit",
  "app": "Ghostty",
  "steps": [{"event_id": 1}, {"event_id": 2}, ...],
  "pattern_count": 3,
  "automation_candidate": true
}
```

```bash
sifu patterns                 # show detected patterns
sifu patterns --today         # today only
sifu patterns --app Ghostty   # filter by app
```

---

## Layer 2: Compiler (LLM-powered)

Takes workflow segments and produces polished SOPs.

### Compilation Process

1. Read workflow segment (events + screenshots)
2. Send event text to LLM (Claude CLI or API) — NO screenshots in prompt by default
3. LLM generates:
   - Title for the workflow
   - Numbered steps with clear action descriptions
   - Which screenshots to include (by event ID)
   - Notes on prerequisites or context
4. Assemble markdown SOP with screenshots

### Output Format

```markdown
# How to: Deploy a Vercel Project from CLI

**Time**: ~2 minutes
**Apps**: Ghostty, Chrome
**Prerequisites**: Vercel CLI installed, logged in

---

## Steps

### 1. Open terminal and navigate to project
![step-1](screenshots/step-001.png)
Opened Ghostty and ran `cd ~/my-project`

### 2. Run Vercel deploy
![step-2](screenshots/step-002.png)
Ran `vercel --prod` — deployment started

### 3. Verify in browser
![step-3](screenshots/step-003.png)
Opened Chrome, navigated to deployment URL, confirmed live
```

### Commands

```bash
sifu compile                    # compile all uncompiled segments
sifu compile --workflow wf-001  # compile specific workflow
sifu compile --today            # compile today's segments
sifu compile --watch            # auto-compile as segments complete
```

---

## Layer 3: Coach

Analyzes patterns and suggests efficiency improvements.

### Coaching Categories

| Category | Example |
|----------|---------|
| **Shortcut suggestion** | "You right-clicked → Copy 14 times today. Cmd+C is faster." |
| **Redundant steps** | "You open System Preferences → Network every morning. Pin it to Dock?" |
| **Tool suggestion** | "This 5-step browser workflow could be a single dev-browser script." |
| **Automation candidate** | "You ran `git add . && git commit -m '...' && git push` 8 times. Alias it." |
| **Workflow optimization** | "You switch between Slack and Ghostty 40x/day. Split screen?" |

### Tool Awareness

The coach knows about these automation tools and suggests them when appropriate:

| Tool | When to Suggest |
|------|----------------|
| **dev-browser / BrowserMonkey** | Repeated browser click sequences (login, form fill, data extraction) |
| **Computer Use (MCP)** | Cross-app workflows that can't be scripted via CLI |
| **Claude CLI** | Text transformation, file processing, content generation patterns |
| **AppleScript / Shortcuts** | macOS-specific app automation (Finder, Mail, Calendar) |
| **Shell aliases/scripts** | Repeated terminal command sequences |
| **Keyboard Maestro** (if installed) | Complex multi-app macros |

### Commands

```bash
sifu coach                    # generate coaching report for this week
sifu coach --today            # today only
sifu coach --focus shortcuts  # specific category
```

---

## Layer 4: Automator

Generates executable automation scripts from identified patterns.

### Script Generation

1. Coach identifies automation candidate
2. LLM generates script using the appropriate tool
3. Script saved to `~/.sifu/automations/` with a README
4. User reviews and approves before first run

### Output Types

| Pattern Type | Generated Script |
|-------------|-----------------|
| Browser workflow | `dev-browser` skill or Computer Use script |
| CLI sequence | Bash script or shell alias |
| File operations | Python script |
| App automation | AppleScript |
| Mixed (cross-app) | Computer Use MCP sequence |

### Commands

```bash
sifu automate                        # list automation candidates
sifu automate --generate wf-001      # generate script for workflow
sifu automate --run my-deploy        # run a saved automation
sifu automate --list                 # list saved automations
```

---

## CLI Interface

```
sifu — your workflow sensei

CAPTURE
  sifu start                Start capture daemon
  sifu stop                 Stop daemon
  sifu pause / resume       Temporarily pause/resume
  sifu status               Daemon status + session stats

REVIEW
  sifu log                  Show today's action log
  sifu log --app Chrome     Filter by app
  sifu log --last 1h        Last hour
  sifu patterns             Show detected patterns
  sifu sessions             List work sessions

COMPILE
  sifu compile              Generate SOPs from segments
  sifu compile --watch      Auto-compile mode
  sifu sops                 List generated SOPs

COACH
  sifu coach                Weekly coaching report
  sifu coach --today        Daily coaching

AUTOMATE
  sifu automate             List automation candidates
  sifu automate --generate  Generate scripts
  sifu automate --run       Run saved automation

CONFIG
  sifu config               Show current config
  sifu config set key val   Update config
  sifu ignore --app Slack   Add app to ignore list
  sifu sensitive            Toggle sensitive mode (pause + clear last 5m)
```

---

## Installation

```bash
# Install globally (available from anywhere)
cd ~/sifu
pip install -e .

# Now works from any directory
sifu start
sifu status
sifu compile
```

### SwiftBar Menu Bar Toggle

Install SwiftBar (`brew install swiftbar`), then symlink the plugin:

```bash
mkdir -p ~/Library/Application\ Support/SwiftBar/Plugins
ln -s ~/sifu/extras/swiftbar/sifu.1s.sh ~/Library/Application\ Support/SwiftBar/Plugins/
```

Menu bar shows:
- **🔴 Sifu** — recording (click for stop/pause/sensitive)
- **⚪ Sifu** — idle (click to start)
- Quick actions: compile SOPs, coach report, show patterns

---

## File Structure

```
sifu/
├── CLAUDE.md               # Agent instructions for this repo
├── PRD.md                  # This document
├── pyproject.toml          # Python package config
├── src/
│   └── sifu/
│       ├── __init__.py
│       ├── cli.py          # Click/argparse CLI entry point
│       ├── daemon.py       # Layer 0: capture daemon
│       ├── events.py       # Event types, schema, serialization
│       ├── capture/
│       │   ├── mouse.py    # Click handler
│       │   ├── keyboard.py # Keystroke + shortcut handler
│       │   ├── apps.py     # App/window tracking
│       │   └── screenshots.py  # Smart screenshot with dedup
│       ├── storage/
│       │   ├── db.py       # SQLite operations
│       │   └── disk.py     # Screenshot storage + FIFO eviction
│       ├── patterns/
│       │   └── engine.py   # Layer 1: sequence detection
│       ├── compiler/
│       │   └── sop.py      # Layer 2: LLM compilation
│       ├── coach/
│       │   ├── analyzer.py # Layer 3: efficiency analysis
│       │   └── tools.py    # Tool awareness (dev-browser, etc.)
│       └── automator/
│           ├── generator.py    # Layer 4: script generation
│           └── templates/      # Script templates per tool type
├── tests/
│   ├── test_capture.py
│   ├── test_patterns.py
│   └── test_compiler.py
├── extras/
│   └── swiftbar/
│       └── sifu.1s.sh      # Menu bar toggle plugin
└── data/
    └── keycodes.json       # macOS keycode mappings
```

---

## Build Plan

### Phase 0: Outer Layer (first)
- Repo scaffold (this PRD, CLAUDE.md, pyproject.toml, directory structure)
- CLI skeleton (all commands defined, help text, no implementation)
- SQLite schema + migration
- Config system (~/.sifu/config.json)

### Phase 1: Capture Daemon
- CGEventTap for clicks + keystrokes
- Accessibility API for element labels
- Smart screenshot with dedup
- SQLite event logging
- `sifu start/stop/status/pause/resume`
- Performance validation (<1% CPU, <30MB RAM)

### Phase 2: Pattern Engine
- Session boundary detection
- Workflow segmentation
- Repeated sequence detection
- `sifu log`, `sifu patterns`, `sifu sessions`

### Phase 3: Compiler
- LLM integration (Claude CLI)
- SOP markdown generation
- Screenshot selection + annotation
- `sifu compile`, `sifu sops`

### Phase 4: Coach
- Shortcut suggestions
- Redundant step detection
- Tool awareness (dev-browser, computer use, CLI)
- `sifu coach`

### Phase 5: Automator
- Script generation from patterns
- Template system per tool type
- `sifu automate`

---

## Security & Privacy

- **All data stays local.** No network calls from the capture daemon. Ever.
- **LLM calls are opt-in** and use local Claude CLI. No screenshots sent to cloud by default.
- **Sensitive mode**: `sifu sensitive` pauses capture and purges last 5 minutes (for passwords, banking, etc.)
- **App ignore list**: configurable, default ignores password managers (1Password, Bitwarden, KeyChain Access)
- **Password field detection**: Accessibility API role="AXSecureTextField" → skip keystroke logging
- **No cloud sync.** If you want to share SOPs, you export them manually.
