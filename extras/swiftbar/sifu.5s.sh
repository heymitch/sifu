#!/bin/bash
# <bitbar.title>Sifu</bitbar.title>
# <bitbar.version>v0.2</bitbar.version>
# <bitbar.author>heymitch</bitbar.author>
# <bitbar.desc>Toggle Sifu action capture from menu bar</bitbar.desc>
# <swiftbar.refreshOnOpen>true</swiftbar.refreshOnOpen>

SIFU_PID_FILE="$HOME/.sifu/daemon.pid"
SIFU_STATE_FILE="$HOME/.sifu/daemon.state"
SIFU_CMD="sifu"

# Check if daemon is running
is_running() {
    if [ -f "$SIFU_PID_FILE" ]; then
        pid=$(cat "$SIFU_PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# Read state directly from JSON file (faster than running sifu status)
read_state() {
    if [ -f "$SIFU_STATE_FILE" ]; then
        python3 -c "
import json, sys
with open('$SIFU_STATE_FILE') as f:
    s = json.load(f)
print(s.get('status','stopped'))
print(s.get('events',0))
print(s.get('session_id',''))
print(s.get('start_time',''))
" 2>/dev/null
    fi
}

# ── Read state ───────────────────────────────────────────
state_lines=$(read_state)
status=$(echo "$state_lines" | sed -n '1p')
events=$(echo "$state_lines" | sed -n '2p')
session=$(echo "$state_lines" | sed -n '3p')
started=$(echo "$state_lines" | sed -n '4p')

# ── Menu Bar Icon ────────────────────────────────────────
if is_running; then
    if [ "$status" = "paused" ]; then
        echo "⏸ Sifu"
    else
        echo "🔴 Sifu | color=#E8682A"
    fi
else
    echo "⚪ Sifu"
fi

echo "---"

# ── Status + Toggle ─────────────────────────────────────
if is_running; then
    if [ "$status" = "paused" ]; then
        echo "Paused — $events events | color=#F5A623"
    else
        echo "Recording — $events events | color=#E8682A"
    fi
    [ -n "$session" ] && echo "$session | size=11 color=#888888"
    [ -n "$started" ] && echo "Since ${started} | size=11 color=#888888"
    echo "---"

    echo "⏹ Stop (+ analyze) | bash=$SIFU_CMD param1=stop terminal=true"

    if [ "$status" = "paused" ]; then
        echo "▶ Resume | bash=$SIFU_CMD param1=resume terminal=false refresh=true"
    else
        echo "⏸ Pause | bash=$SIFU_CMD param1=pause terminal=false refresh=true"
    fi

    echo "🔒 Sensitive (purge 5m) | bash=$SIFU_CMD param1=sensitive terminal=false refresh=true"
else
    echo "Not recording | color=#888888"
    echo "---"
    echo "▶ Start Recording | bash=$SIFU_CMD param1=start terminal=false refresh=true"
fi

echo "---"

# ── Quick Actions ────────────────────────────────────────
echo "📋 Compile SOPs | bash=$SIFU_CMD param1=compile terminal=true"
echo "🎯 Coach Report | bash=$SIFU_CMD param1=coach param2=--today terminal=true"
echo "📊 Show Patterns | bash=$SIFU_CMD param1=patterns param2=--today terminal=true"
echo "📝 Show Log | bash=$SIFU_CMD param1=log param2=--last param3=1h terminal=true"
echo "---"
echo "⚙️ Config | bash=$SIFU_CMD param1=config terminal=true"
echo "📂 Open Data | bash=open param1=$HOME/.sifu/ terminal=false"
