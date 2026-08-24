#!/bin/bash
# Sifu one-step installer — macOS only.
#
# Idempotent: safe to re-run. Installs the Python package (with the UI extra),
# runs bootstrap, builds and installs SifuBar.app, and points you at the two
# permissions macOS will not let a script grant on your behalf.
#
#   ./install.sh              full install
#   ./install.sh --skip-app   Python side only, leave SifuBar.app alone
#   ./install.sh --no-launch  install everything, don't start SifuBar
#
# Why --skip-app exists: without an Apple Development certificate, SifuBar is
# ad-hoc signed, and TCC keys Accessibility/Screen Recording to the signature.
# Every rebuild therefore revokes both permissions. This script only reinstalls
# the app when the built binary actually differs from the installed one, so a
# routine re-run costs you nothing.

set -euo pipefail

cd "$(dirname "$0")"
REPO="$(pwd)"

SKIP_APP=0
NO_LAUNCH=0
for arg in "$@"; do
    case "$arg" in
        --skip-app)  SKIP_APP=1 ;;
        --no-launch) NO_LAUNCH=1 ;;
        -h|--help)   awk 'NR>1 && /^#/ {sub(/^# ?/,""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 64 ;;
    esac
done

say()  { printf '\n\033[1m%s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }

# ---------------------------------------------------------------- platform

if [ "$(uname -s)" != "Darwin" ]; then
    echo "Sifu is macOS only — it uses CGEventTap and the Accessibility API." >&2
    exit 1
fi

# ---------------------------------------------------------------- python

say "Python package"

PY=""
for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
        PY="$c"; break
    fi
done
if [ -z "$PY" ]; then
    echo "Python 3.11+ required (pyproject sets requires-python >=3.11)." >&2
    exit 1
fi
ok "$($PY --version) at $(command -v "$PY")"

# The [ui] extra carries the local library browser. Installing without it is
# the single most common way to end up with a working CLI and a dead `sifu ui`.
"$PY" -m pip install -e ".[ui]" --quiet
ok "sifu installed (editable, with [ui] extra)"

# ---------------------------------------------------------------- bootstrap

say "Library"
BOOT="$("$PY" -c 'from sifu.install.bootstrap import run; import json; print(json.dumps(run()))')"
LIBRARY="$("$PY" -c "import json,sys; print(json.loads(sys.argv[1])['library'])" "$BOOT")"
NEXT="$("$PY" -c "import json,sys; print(json.loads(sys.argv[1])['next'])" "$BOOT")"
ok "library: $LIBRARY"

# ---------------------------------------------------------------- menu bar app

APP_INSTALLED="/Applications/SifuBar.app"
APP_BUILT="$REPO/extras/SifuBar/build/SifuBar.app"
APP_CHANGED=0

if [ "$SKIP_APP" -eq 1 ]; then
    say "SifuBar.app"
    warn "skipped (--skip-app)"
else
    say "SifuBar.app"
    if ! command -v swift >/dev/null 2>&1; then
        warn "swift not found — skipping the menu bar app (install Xcode command line tools)"
    else
        # Keep the build quiet, but don't swallow a real failure: codesign
        # chatters on stderr even when it succeeds, so log both streams and
        # only surface them if the build actually exits non-zero.
        BUILD_LOG="$(mktemp -t sifubar-build)"
        if ! ./extras/SifuBar/build-app.sh >"$BUILD_LOG" 2>&1; then
            echo "SifuBar build failed:" >&2
            cat "$BUILD_LOG" >&2
            rm -f "$BUILD_LOG"
            exit 1
        fi
        rm -f "$BUILD_LOG"
        ok "built"

        # Only replace the installed app when the binary actually differs.
        # Reinstalling an identical build would still change nothing, but
        # reinstalling a *different* one silently revokes TCC permissions,
        # so make the cost explicit rather than incidental.
        NEW_HASH="$(shasum -a256 "$APP_BUILT/Contents/MacOS/SifuBar" | awk '{print $1}')"
        OLD_HASH=""
        [ -x "$APP_INSTALLED/Contents/MacOS/SifuBar" ] && \
            OLD_HASH="$(shasum -a256 "$APP_INSTALLED/Contents/MacOS/SifuBar" | awk '{print $1}')"

        if [ "$NEW_HASH" = "$OLD_HASH" ]; then
            ok "already current — not reinstalling (permissions preserved)"
        else
            osascript -e 'quit app "SifuBar"' >/dev/null 2>&1 || true
            sleep 1
            pkill -x SifuBar >/dev/null 2>&1 || true
            rm -rf "$APP_INSTALLED"
            cp -R "$APP_BUILT" /Applications/
            APP_CHANGED=1
            ok "installed → $APP_INSTALLED"
            if [ -n "$OLD_HASH" ]; then
                warn "binary changed — macOS has revoked Accessibility and Screen Recording"
            fi
        fi

        if codesign -dv "$APP_INSTALLED" 2>&1 | grep -q "adhoc"; then
            warn "ad-hoc signed: every rebuild revokes permissions."
            warn "A free Apple Development cert in Xcode makes them persist."
        fi

        if [ "$NO_LAUNCH" -eq 0 ] && ! pgrep -x SifuBar >/dev/null 2>&1; then
            open "$APP_INSTALLED"
            sleep 2
            pgrep -x SifuBar >/dev/null 2>&1 && ok "running"
        fi
    fi
fi

# ---------------------------------------------------------------- permissions

say "Permissions"

PERMS="$HOME/.sifu/permissions.json"
GRANTED=0
if [ "$APP_CHANGED" -eq 0 ] && [ -f "$PERMS" ] && \
   grep -q '"accessibility":[[:space:]]*true' "$PERMS" && \
   grep -q '"screen_recording":[[:space:]]*true' "$PERMS"; then
    GRANTED=1
fi

if [ "$GRANTED" -eq 1 ]; then
    ok "Accessibility and Screen Recording already granted"
else
    # Deliberately not opening System Settings here. Granting through the app's
    # own menu item runs PermissionManager.checkAndRequest, which opens the
    # correct panes *and* starts the poll that records the grant in
    # permissions.json. Granting manually skips that poll and the app can sit
    # stale until it is restarted.
    warn "not granted yet — do this in the menu, not System Settings:"
    echo "      SifuBar (◇) → \"⚠️ Permissions needed to record\""
    echo "      grant Accessibility + Screen Recording in the panes it opens"
    echo "      then hit Restart in the same menu"
fi

# ---------------------------------------------------------------- done

say "Done"
echo "  $NEXT"
echo
echo "  sifu ui        local library browser"
echo "  sifu status    daemon + current session"
echo "  sifu context <query>   hand a recorded workflow to your agent"
