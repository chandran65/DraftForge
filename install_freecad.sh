#!/bin/bash
set -e

DMG_URL="https://github.com/FreeCAD/FreeCAD/releases/download/1.1.1/FreeCAD_1.1.1-macOS-arm64-py311.dmg"
DMG_FILE="FreeCAD_1.1.1-macOS-arm64-py311.dmg"
MOUNT_POINT="/Volumes/FreeCAD_1.1.1"

echo "=== Step 1: Downloading FreeCAD 1.1.1 DMG (arm64) ==="
if [ ! -f "$DMG_FILE" ]; then
    curl -L -o "$DMG_FILE" "$DMG_URL"
else
    echo "DMG already downloaded, skipping download."
fi

echo "=== Step 2: Mounting FreeCAD DMG ==="
# Check if already mounted
if [ -d "$MOUNT_POINT" ]; then
    echo "Already mounted, unmounting first..."
    hdiutil detach "$MOUNT_POINT" || true
fi

echo "Attaching DMG..."
hdiutil attach "$DMG_FILE" -mountpoint "$MOUNT_POINT" -nobrowse

echo "=== Step 3: Installing FreeCAD.app to /Applications ==="
if [ -d "/Applications/FreeCAD.app" ]; then
    echo "Old FreeCAD.app exists, removing it..."
    rm -rf "/Applications/FreeCAD.app"
fi

echo "Copying FreeCAD.app to /Applications..."
cp -R "$MOUNT_POINT/FreeCAD.app" "/Applications/"

echo "=== Step 4: Detaching DMG ==="
hdiutil detach "$MOUNT_POINT"

echo "=== Step 5: Removing quarantine attribute ==="
xattr -r -d com.apple.quarantine "/Applications/FreeCAD.app" || true

echo "=== FreeCAD Installation Complete! ==="
ls -ld "/Applications/FreeCAD.app"
