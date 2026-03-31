#!/bin/bash
# <bitbar.title>Sifu</bitbar.title>
# <bitbar.version>v0.1</bitbar.version>
# <bitbar.author>heymitch</bitbar.author>
# <bitbar.desc>Toggle Sifu action capture from menu bar</bitbar.desc>
# <swiftbar.refreshOnOpen>true</swiftbar.refreshOnOpen>

SIFU_PID_FILE="$HOME/.sifu/daemon.pid"
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

# Get session stats from sifu status
get_stats() {
    if command -v $SIFU_CMD &>/dev/null; then
        $SIFU_CMD status --json 2>/dev/null
    fi
}

# ── Menu Bar Icon ────────────────────────────────────────
if is_running; then
    echo "🔴 Sifu"
else
    echo "⚪ Sifu"
fi

echo "---"

# ── Toggle ───────────────────────────────────────────────
if is_running; then
    stats=$(get_stats)
    steps=$(echo "$stats" | python3 -c "import sys,json; print(json.load(sys.stdin).get('steps',0))" 2>/dev/null || echo "?")
    duration=$(echo "$stats" | python3 -c "import sys,json; d=json.load(sys.stdin).get('duration_min',0); print(f'{d:.0f}m')" 2>/dev/null || echo "?")

    echo "Recording — $steps steps ($duration) | color=#E8682A"
    echo "---"
    echo "⏹ Stop Recording | bash=$SIFU_CMD param1=stop terminal=false refresh=true"
    echo "⏸ Pause | bash=$SIFU_CMD param1=pause terminal=false refresh=true"
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
echo "---"
echo "⚙️ Open Config | bash=open param1=$HOME/.sifu/ terminal=false"
echo "📂 Open SOPs | bash=open param1=$HOME/.sifu/output/sops/ terminal=false"
