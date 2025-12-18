# Qdrant Manager Installers

This directory contains installer packages for Qdrant Manager on Windows and Ubuntu/Debian systems.

## Windows Installer (setup.exe)

### Prerequisites

1. **Build the executable first:**
   ```cmd
   cd ..
   build_windows.bat
   ```

2. **Install Inno Setup:**
   - Download from: https://jrsoftware.org/isinfo.php
   - Install to default location: `C:\Program Files (x86)\Inno Setup 6\`

### Building the Installer

```cmd
cd installers
build_windows_installer.bat
```

The installer will be created at: `dist\installers\QdrantManager-Setup.exe`

### Features

- ✅ License agreement (must be accepted before installation)
- ✅ Automatic installation to Program Files
- ✅ Desktop shortcut (optional)
- ✅ Start menu entry
- ✅ Option to launch Qdrant Manager after installation
- ✅ Uninstaller support

### Installation

Users can simply double-click `QdrantManager-Setup.exe` and follow the wizard:
1. Accept the license agreement
2. Choose installation directory (default: `C:\Program Files\Qdrant Manager`)
3. Select additional options (desktop icon, etc.)
4. Complete installation
5. Optionally launch Qdrant Manager immediately

## Ubuntu/Debian Installer (.deb package)

### Prerequisites

1. **Build the executable first:**
   ```bash
   cd ..
   ./build_linux.sh
   ```

2. **Install required tools:**
   ```bash
   sudo apt-get update
   sudo apt-get install dpkg-dev fakeroot
   ```

### Building the Package

```bash
cd installers
chmod +x build_ubuntu_installer.sh
./build_ubuntu_installer.sh
```

The package will be created at: `dist/installers/qdrant-manager_0.1.0-1_amd64.deb`

### Features

- ✅ License agreement display during installation
- ✅ Desktop integration (application menu entry)
- ✅ Icon support
- ✅ Post-install script to launch application (optional)
- ✅ Proper package management integration

### Installation

**Option 1: Using dpkg (command line)**
```bash
sudo dpkg -i dist/installers/qdrant-manager_0.1.0-1_amd64.deb
```

**Option 2: Using gdebi (GUI installer with dependency resolution)**
```bash
sudo apt-get install gdebi
sudo gdebi dist/installers/qdrant-manager_0.1.0-1_amd64.deb
```

**Option 3: Using Software Center (Ubuntu)**
- Double-click the `.deb` file
- Click "Install" in Software Center
- Enter your password when prompted

### Uninstallation

**Windows:**
- Use "Add or Remove Programs" in Windows Settings
- Or run the uninstaller from Start Menu

**Ubuntu/Debian:**
```bash
sudo apt-get remove qdrant-manager
```

## License Agreement

Both installers include the MIT License agreement. Users must accept the license terms before installation can proceed.

## Troubleshooting

### Windows Installer

**Issue: Inno Setup not found**
- Solution: Install Inno Setup from https://jrsoftware.org/isinfo.php
- Make sure it's installed to the default location

**Issue: Executable not found**
- Solution: Build the executable first using `build_windows.bat`

### Ubuntu Installer

**Issue: dpkg-deb not found**
- Solution: Install dpkg-dev: `sudo apt-get install dpkg-dev`

**Issue: fakeroot not found**
- Solution: Install fakeroot: `sudo apt-get install fakeroot`

**Issue: Package installation fails**
- Solution: Check dependencies: `sudo apt-get install -f`

## Customization

### Windows Installer

Edit `installers/windows/QdrantManager.iss` to customize:
- Application name and version
- Installation directory
- License file location
- Icons and shortcuts
- Post-install actions

### Ubuntu Installer

Edit files in `installers/ubuntu/debian/`:
- `control`: Package metadata and dependencies
- `changelog`: Version history
- `postinst`: Post-installation script
- `preinst`: Pre-installation script (license display)

## Distribution

After building the installers, you can distribute them to users:

- **Windows**: Share `dist/installers/QdrantManager-Setup.exe`
- **Ubuntu/Debian**: Share `dist/installers/qdrant-manager_0.1.0-1_amd64.deb`

Users don't need Python or any dependencies installed - everything is bundled in the installers.

