#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Building SifuBar..."
swift build -c release

APP_DIR="build/SifuBar.app/Contents"
mkdir -p "$APP_DIR/MacOS"

cp .build/release/SifuBar "$APP_DIR/MacOS/SifuBar"
cp SifuBar/Info.plist "$APP_DIR/Info.plist"

# Code sign with a stable identity so macOS preserves Accessibility
# trust across rebuilds. Falls back to ad-hoc if no cert is available.
# Only lines listing a real identity carry a quoted name; "0 valid identities
# found" has no quotes, so awk yields an empty string and we fall through to
# ad-hoc. (The old `head -1 | sed` kept the line's leading whitespace, so the
# literal-string guard below never matched and codesign was handed
# "     0 valid identities found" as an identity name — it errored out and
# set -e killed the script before the bundle was ever signed.)
SIGN_IDENTITY=$(security find-identity -v -p codesigning 2>/dev/null | awk -F'"' '/"/ {print $2; exit}' || true)

if [ -n "$SIGN_IDENTITY" ]; then
    echo "Signing with: $SIGN_IDENTITY"
    codesign --force --sign "$SIGN_IDENTITY" --deep "build/SifuBar.app"
else
    echo "No signing identity found — using ad-hoc (permissions reset on rebuild)"
    codesign --force --sign - --deep "build/SifuBar.app"
fi

echo ""
echo "Built: build/SifuBar.app"
echo "To install: cp -r build/SifuBar.app /Applications/"
echo "To run:     open build/SifuBar.app"
