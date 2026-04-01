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

## Menu bar

The menu bar widget launches **automatically** with `sifu start`. No setup needed.

It uses SifuBar (a native Python widget bundled with Sifu) that works on all macOS versions including Tahoe. Falls back to SwiftBar if installed.

You can also launch it standalone: `sifubar`

Shows recording status in the menu bar:
- **◉ Sifu** — recording (click for stop/pause/sensitive)
- **◎ Sifu** — paused
- **◇ Sifu** — idle (click to start)

## Classify — optimize workflows for automation

Discover what tools you have and classify each step of a recorded workflow into the most efficient execution method.

```bash
# Show what automation tools are available
sifu classify --discover

# Classify a specific workflow
sifu classify wf-2026-03-31-001

# Classify all workflows
sifu classify --all

# Re-classify after adding new capabilities
sifu classify --reclassify ~/.sifu/output/workflows/deploy.workflow.yaml

# See what would change
sifu classify --diff ~/.sifu/output/workflows/deploy.workflow.yaml
```

### Custom capabilities

Drop YAML files in `~/.sifu/capabilities.d/` to teach the classifier about your tools:

```yaml
# ~/.sifu/capabilities.d/slack.yaml
name: slack
type: mcp
description: "Slack messaging"
matches:
  - app: "Slack"
  - url_contains: "slack.com"
actions:
  - send_message
  - read_channel
```

See `examples/capabilities.d/` for more examples.

## Privacy

- All data stays local. The daemon makes zero network calls.
- LLM calls use Claude CLI locally. No screenshots sent to cloud.
- `sifu sensitive` purges the last 5 minutes of data instantly.
- Password fields (AXSecureTextField) are never logged.
- 1Password, Bitwarden, and KeyChain Access are ignored by default.
