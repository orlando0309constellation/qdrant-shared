#!/bin/bash
# Build Ubuntu/Debian Installer (.deb package) for Qdrant Manager
# This script creates a .deb package with license agreement and post-install launch

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
INSTALLER_DIR="$SCRIPT_DIR/ubuntu"
DEBIAN_DIR="$INSTALLER_DIR/debian"

echo "========================================"
echo "Building Ubuntu/Debian Installer for Qdrant Manager"
echo "========================================"
echo ""

# Check if executable exists
if [ ! -f "$PROJECT_ROOT/dist/QdrantManager" ]; then
    echo "ERROR: QdrantManager executable not found in dist folder"
    echo "Please build the executable first using: ./build_linux.sh"
    exit 1
fi

# Check if required tools are installed
if ! command -v dpkg-deb &> /dev/null; then
    echo "ERROR: dpkg-deb not found. Please install dpkg-dev:"
    echo "  sudo apt-get install dpkg-dev"
    exit 1
fi

if ! command -v fakeroot &> /dev/null; then
    echo "ERROR: fakeroot not found. Please install fakeroot:"
    echo "  sudo apt-get install fakeroot"
    exit 1
fi

# Check if license file exists
if [ ! -f "$PROJECT_ROOT/LICENSE.txt" ]; then
    echo "ERROR: LICENSE.txt not found in project root"
    exit 1
fi

# Make scripts executable
chmod +x "$DEBIAN_DIR/rules"
chmod +x "$DEBIAN_DIR/postinst"
chmod +x "$DEBIAN_DIR/postrm"
chmod +x "$DEBIAN_DIR/preinst"

# Create build directory
BUILD_DIR="$INSTALLER_DIR/build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Copy debian directory to build location
cp -r "$DEBIAN_DIR" "$BUILD_DIR/"

# Copy license to debian package
mkdir -p "$BUILD_DIR/debian/qdrant-manager/usr/share/doc/qdrant-manager"
cp "$PROJECT_ROOT/LICENSE.txt" "$BUILD_DIR/debian/qdrant-manager/usr/share/doc/qdrant-manager/copyright"

# Copy executable to a location accessible from the build directory
# The rules file will copy it from PROJECT_ROOT/dist/QdrantManager
# We need to create a symlink or adjust the path in rules
# For now, let's modify the rules to use absolute path or copy it first
mkdir -p "$BUILD_DIR/tmp"
cp "$PROJECT_ROOT/dist/QdrantManager" "$BUILD_DIR/tmp/QdrantManager"
chmod +x "$BUILD_DIR/tmp/QdrantManager"

# Also copy icon and desktop file to accessible location
cp "$PROJECT_ROOT/qdrant_distributed/interface/image/qdrant-icon-seeklogo.png" "$BUILD_DIR/tmp/qdrant-icon-seeklogo.png"

# Update rules file to use the temp location
sed -i "s|@EXECUTABLE_PATH@|$BUILD_DIR/tmp/QdrantManager|g" "$BUILD_DIR/debian/rules"
sed -i "s|@ICON_PATH@|$BUILD_DIR/tmp/qdrant-icon-seeklogo.png|g" "$BUILD_DIR/debian/rules"

# Build the package
echo "Building Debian package..."
cd "$BUILD_DIR"

# Use fakeroot to build the package
fakeroot dpkg-deb --build debian qdrant-manager_0.1.0-1_amd64.deb

if [ $? -eq 0 ]; then
    # Move package to dist/installers
    mkdir -p "$PROJECT_ROOT/dist/installers"
    mv qdrant-manager_0.1.0-1_amd64.deb "$PROJECT_ROOT/dist/installers/"
    
    echo ""
    echo "========================================"
    echo "Package built successfully!"
    echo "========================================"
    echo ""
    echo "Package location: $PROJECT_ROOT/dist/installers/qdrant-manager_0.1.0-1_amd64.deb"
    echo ""
    echo "To install the package:"
    echo "  sudo dpkg -i $PROJECT_ROOT/dist/installers/qdrant-manager_0.1.0-1_amd64.deb"
    echo ""
    echo "Or use gdebi for a GUI installer:"
    echo "  sudo gdebi $PROJECT_ROOT/dist/installers/qdrant-manager_0.1.0-1_amd64.deb"
    echo ""
    echo "The package includes:"
    echo "  - License agreement display during installation"
    echo "  - Automatic desktop integration"
    echo "  - Option to launch Qdrant Manager after installation"
    echo ""
else
    echo ""
    echo "ERROR: Package build failed!"
    exit 1
fi

# Cleanup
cd "$PROJECT_ROOT"
rm -rf "$BUILD_DIR"

