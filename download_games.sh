#!/bin/bash
set -e

REPO_ZIP_URL="https://github.com/BYU-PCCL/z-machine-games/archive/refs/heads/master.zip"
TARGET_DIR="games"

echo "Downloading z-machine games..."

TEMP_DIR=$(mktemp -d)
ZIP_PATH="$TEMP_DIR/z-machine-games.zip"

curl -L "$REPO_ZIP_URL" -o "$ZIP_PATH"

echo "Extracting games..."

unzip -q "$ZIP_PATH" -d "$TEMP_DIR"

mkdir -p "$TARGET_DIR"
rsync -av --exclude="*/" "$TEMP_DIR/z-machine-games-master/" "$TARGET_DIR/"

echo "Cleaning up..."
rm -rf "$TEMP_DIR"

echo "Done! Games are now in ./$TARGET_DIR"
