# Sifu

Local action logger that turns your workflow into SOPs, coaching feedback, and automation scripts.

Leave Sifu on for a day. At the end you have:
- Every workflow documented as a step-by-step SOP
- Coaching feedback on inefficiencies ("use Cmd+C instead of right-click > Copy")
- Automation scripts for repeatable patterns

## Requirements

- macOS (uses CGEventTap + Accessibility API)
- Python 3.11+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (for SOP compilation + coaching)
- Accessibility permission (System Settings > Privacy & Security > Accessibility)

## Install

```bash
git clone https://github.com/heymitch/sifu.git ~/sifu
cd ~/sifu
pip install -e .
```

## How it works

```
sifu start       →  capture daemon runs in background
                     (clicks, keystrokes, shortcuts, app switches, screenshots)
do your work     →  Sifu watches silently (<1% CPU, ~30MB RAM)
sifu stop        →  daemon stops → patterns detected → SOPs compiled
                     → each SOP opens in Sublime Text → macOS notification
```

That's it. Start, work, stop, SOPs appear.

## Commands

```bash
# Capture
sifu start           # start capture daemon (background)
sifu stop            # stop + auto-compile SOPs + coaching
sifu status          # is it running? how many events?
sifu pause / resume  # temporarily pause capture

# Review
sifu log             # show today's action log
sifu patterns        # detected workflow patterns
sifu sessions        # list work sessions

# Generate (uses Claude Code)
sifu compile         # generate SOPs from patterns
sifu coach --today   # efficiency coaching report
sifu automate        # list automation candidates

# Config
sifu config          # show/edit settings
sifu sensitive       # panic button: pause + purge last 5 min
```

## Where SOPs are saved

By default, compiled SOPs land in `~/.sifu/output/sops/`. To save them somewhere more visible (a shared folder, a knowledge base, Obsidian vault, etc.):

```bash
sifu config sops_dir ~/path/to/your/sops-folder
```

Compiled SOPs auto-open in Sublime Text and you get a macOS notification when compilation finishes.

## Menu bar (SwiftBar)

SwiftBar setup is **automatic** — the first time you run `sifu start`, it detects SwiftBar and installs the plugin. If SwiftBar isn't running, it launches it.

If you don't have SwiftBar: `brew install swiftbar`

Shows recording status in the menu bar:
- **🔴 Sifu** — recording (click for stop/pause/sensitive)
- **⏸ Sifu** — paused
- **⚪ Sifu** — idle (click to start)

## Privacy

- All data stays local. The daemon makes zero network calls.
- LLM calls use Claude CLI locally. No screenshots sent to cloud.
- `sifu sensitive` purges the last 5 minutes of data instantly.
- Password fields (AXSecureTextField) are never logged.
- 1Password, Bitwarden, and KeyChain Access are ignored by default.
