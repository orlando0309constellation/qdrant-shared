#!/bin/bash
# Enhanced Linux build script for Qdrant Manager
# Supports both PyInstaller and Nuitka

set -e

BUILD_TOOL="${1:-pyinstaller}"

echo "========================================"
echo "Building Qdrant Manager for Linux"
echo "========================================"
echo
echo "Using build tool: $BUILD_TOOL"
echo

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found"
    exit 1
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist build *.spec __pycache__
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

if [ "$BUILD_TOOL" == "auto" ]; then
    echo
    echo "Installing auto-py-to-exe..."
    pip3 install auto-py-to-exe
    echo "Opening auto-py-to-exe GUI..."
    auto-py-to-exe
    exit 0
fi

if [ "$BUILD_TOOL" == "nuitka" ]; then
    echo
    echo "Installing/updating Nuitka..."
    pip3 install nuitka
    
    echo "Building with Nuitka..."
    python3 build_nuitka.py
    if [ $? -eq 0 ]; then
        chmod +x dist/QdrantManager
        echo
        echo "✅ Build completed successfully!"
        echo "Executable location: dist/QdrantManager"
    fi
    exit $?
fi

# PyInstaller build
echo "Installing/updating PyInstaller..."
pip3 install pyinstaller

# Check for tkinter
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo
    echo "WARNING: tkinter not found!"
    echo "Installing tkinter..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get install -y python3-tk
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3-tkinter
    elif command -v pacman &> /dev/null; then
        sudo pacman -S tk
    else
        echo "Please install python3-tk manually for your distribution"
    fi
fi

echo
echo "Building executable with PyInstaller..."
echo "Using simple build script (no spec file needed)..."
python3 build_simple.py
BUILD_STATUS=$?

if [ $BUILD_STATUS -ne 0 ]; then
    echo
    echo "Build failed! Trying alternative method with spec file..."
    if [ -f "build.spec" ]; then
        pyinstaller build.spec --clean --noconfirm
        BUILD_STATUS=$?
        if [ $BUILD_STATUS -ne 0 ]; then
            exit 1
        fi
    else
        echo "ERROR: build.spec not found and simple build failed"
        exit 1
    fi
fi

if [ $? -ne 0 ]; then
    echo
    echo "❌ Build failed!"
    echo
    echo "Troubleshooting:"
    echo "1. Make sure all dependencies are installed: pip3 install -e '.[all-db]'"
    echo "2. Install tkinter: sudo apt-get install python3-tk (Ubuntu/Debian)"
    echo "3. Check that build.spec exists"
    exit 1
fi

chmod +x dist/QdrantManager

echo
echo "========================================"
echo "✅ Build completed successfully!"
echo "========================================"
echo
echo "Executable location: dist/QdrantManager"
if [ -f "dist/QdrantManager" ]; then
    echo "File size: $(du -h dist/QdrantManager | cut -f1)"
fi
echo
echo "To test: ./dist/QdrantManager"
echo
