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
SIGN_IDENTITY=$(security find-identity -v -p codesigning 2>/dev/null | head -1 | sed 's/.*"\(.*\)".*/\1/' || true)

if [ -n "$SIGN_IDENTITY" ] && [ "$SIGN_IDENTITY" != "0 valid identities found" ]; then
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
