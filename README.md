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
git clone <repo-url> ~/sifu
cd ~/sifu
pip install -e .
```

## Usage

```bash
sifu start           # start capture daemon (background)
sifu stop            # stop + auto-analyze session
sifu status          # is it running? how many events?
sifu pause / resume  # temporarily pause capture

sifu log             # show today's action log
sifu patterns        # detected workflow patterns
sifu compile         # generate SOPs from patterns (uses Claude)
sifu coach --today   # efficiency coaching report (uses Claude)
sifu automate        # list automation candidates

sifu sensitive       # panic button: pause + purge last 5 min
sifu config          # show/edit settings
```

## SwiftBar (menu bar toggle)

```bash
brew install swiftbar
ln -s ~/sifu/extras/swiftbar/sifu.5s.sh \
  ~/Library/Application\ Support/SwiftBar/Plugins/
```

## Privacy

- All data stays local. The daemon makes zero network calls.
- LLM calls use Claude CLI locally. No screenshots sent to cloud.
- `sifu sensitive` purges the last 5 minutes of data instantly.
- Password fields (AXSecureTextField) are never logged.
- 1Password, Bitwarden, and KeyChain Access are ignored by default.
