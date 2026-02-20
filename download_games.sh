#!/bin/bash
set -e

REPO_ZIP_URL="https://github.com/BYU-PCCL/z-machine-games/archive/refs/heads/master.zip"
TARGET_DIR="games"

echo "Downloading z-machine games..."

TEMP_DIR=$(mktemp -d)
ZIP_PATH="$TEMP_DIR/z-machine-games.zip"

curl -L "$REPO_ZIP_URL" -o "$ZIP_PATH"

echo "Extracting repository..."
unzip -q "$ZIP_PATH" -d "$TEMP_DIR"

mkdir -p "$TARGET_DIR"

rsync -a "$TEMP_DIR/z-machine-games-master/" "$TARGET_DIR/"

echo "Extracting large game collection..."
unzip -oq "$TARGET_DIR/the-large-game-collection.zip" -d "$TARGET_DIR"
echo "Removing zip file..."
rm "$TARGET_DIR/the-large-game-collection.zip"

echo "Cleaning up temp files..."
rm -rf "$TEMP_DIR"

echo "Done! All games are extracted into ./$TARGET_DIR"