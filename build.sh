#!/bin/bash

# MekaBox Build Script
# Bundles Python backend and packages Electron app

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ELECTRON_DIR="$SCRIPT_DIR/electron-app"
RESOURCES_DIR="$ELECTRON_DIR/resources"

echo "========================================="
echo "MekaBox Build Script"
echo "========================================="

# Check for required tools
echo "Checking dependencies..."

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required but not installed."
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "Error: npm is required but not installed."
    exit 1
fi

# Install PyInstaller if needed
if ! python3 -c "import PyInstaller" &> /dev/null; then
    echo "Installing PyInstaller..."
    pip3 install pyinstaller
fi

# Step 1: Bundle Python backend
echo ""
echo "Step 1: Bundling Python backend..."
echo "-----------------------------------------"

cd "$SCRIPT_DIR"
mkdir -p "$RESOURCES_DIR"

# Build for current platform
pyinstaller --onefile \
    --name mekabox-backend \
    --distpath "$RESOURCES_DIR" \
    --clean \
    mekabox_cli.py

echo "Backend bundled successfully!"

# Step 2: Install npm dependencies
echo ""
echo "Step 2: Installing npm dependencies..."
echo "-----------------------------------------"

cd "$ELECTRON_DIR"
npm install

# Step 3: Build Electron app
echo ""
echo "Step 3: Building Electron app..."
echo "-----------------------------------------"

# Parse arguments
BUILD_TARGET="${1:-mac}"

case "$BUILD_TARGET" in
    mac)
        echo "Building for macOS..."
        npm run build:mac
        ;;
    win)
        echo "Building for Windows..."
        npm run build:win
        ;;
    linux)
        echo "Building for Linux..."
        npm run build:linux
        ;;
    all)
        echo "Building for all platforms..."
        npm run build
        ;;
    *)
        echo "Unknown target: $BUILD_TARGET"
        echo "Usage: ./build.sh [mac|win|linux|all]"
        exit 1
        ;;
esac

echo ""
echo "========================================="
echo "Build complete!"
echo "Output files are in: $ELECTRON_DIR/dist/"
echo "========================================="

ls -la "$ELECTRON_DIR/dist/" 2>/dev/null || echo "(No output files yet)"
