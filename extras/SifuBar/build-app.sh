#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Building SifuBar..."
swift build -c release

APP_DIR="build/SifuBar.app/Contents"
mkdir -p "$APP_DIR/MacOS"

cp .build/release/SifuBar "$APP_DIR/MacOS/SifuBar"
cp SifuBar/Info.plist "$APP_DIR/Info.plist"

echo "Built: build/SifuBar.app"
echo ""
echo "To install: cp -r build/SifuBar.app /Applications/"
echo "To run:     open build/SifuBar.app"
