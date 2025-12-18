# Building Installers for Qdrant Manager

This guide explains how to build installer packages for Windows and Ubuntu/Debian systems.

## Quick Start

### Windows Installer

1. **Build the executable:**
   ```cmd
   build_windows.bat
   ```

2. **Install Inno Setup** (if not already installed):
   - Download from: https://jrsoftware.org/isinfo.php
   - Install to default location

3. **Build the installer:**
   ```cmd
   cd installers
   build_windows_installer.bat
   ```

   The installer will be at: `dist\installers\QdrantManager-Setup.exe`

### Ubuntu/Debian Installer

1. **Build the executable:**
   ```bash
   ./build_linux.sh
   ```

2. **Install required tools:**
   ```bash
   sudo apt-get update
   sudo apt-get install dpkg-dev fakeroot
   ```

3. **Build the package:**
   ```bash
   cd installers
   chmod +x build_ubuntu_installer.sh
   ./build_ubuntu_installer.sh
   ```

   The package will be at: `dist/installers/qdrant-manager_0.1.0-1_amd64.deb`

## Features

Both installers include:

✅ **License Agreement** - Users must accept the MIT License before installation  
✅ **Automatic Installation** - Simple wizard-based installation process  
✅ **Post-Install Launch** - Option to launch Qdrant Manager immediately after installation  
✅ **Desktop Integration** - Icons, shortcuts, and menu entries  
✅ **Uninstaller Support** - Easy removal through system tools  

## Windows Installer Details

### Requirements
- Windows 10/11 (64-bit)
- Inno Setup 6.x
- Built executable (`dist\QdrantManager.exe`)

### Installation Process
1. User double-clicks `QdrantManager-Setup.exe`
2. License agreement is displayed (must accept)
3. Installation directory selection (default: `C:\Program Files\Qdrant Manager`)
4. Optional components (desktop icon, quick launch)
5. Installation completes
6. Option to launch Qdrant Manager immediately

### Customization
Edit `installers/windows/QdrantManager.iss` to modify:
- Application name, version, publisher
- Installation directory
- License file location
- Icons and shortcuts
- Post-install actions

## Ubuntu/Debian Installer Details

### Requirements
- Ubuntu 18.04+ or Debian 10+
- dpkg-dev and fakeroot packages
- Built executable (`dist/QdrantManager`)

### Installation Process

**Using dpkg:**
```bash
sudo dpkg -i dist/installers/qdrant-manager_0.1.0-1_amd64.deb
```

**Using gdebi (recommended - handles dependencies):**
```bash
sudo apt-get install gdebi
sudo gdebi dist/installers/qdrant-manager_0.1.0-1_amd64.deb
```

**Using Software Center:**
- Double-click the `.deb` file
- Click "Install" in Software Center

### Customization
Edit files in `installers/ubuntu/debian/`:
- `control` - Package metadata, dependencies
- `changelog` - Version history
- `postinst` - Post-installation script (launch prompt)
- `preinst` - Pre-installation script (license display)
- `rules` - Build rules and file installation

## License Agreement

Both installers display the MIT License agreement:
- **Windows**: Shown in the installer wizard (must accept to continue)
- **Ubuntu/Debian**: Displayed in terminal during installation via `preinst` script

The license text is in `LICENSE.txt` at the project root.

## Distribution

After building, distribute the installers:

- **Windows**: `dist/installers/QdrantManager-Setup.exe`
- **Ubuntu/Debian**: `dist/installers/qdrant-manager_0.1.0-1_amd64.deb`

Users don't need Python or any dependencies - everything is bundled!

## Troubleshooting

### Windows

**"Inno Setup not found"**
- Install Inno Setup from https://jrsoftware.org/isinfo.php
- Ensure it's in the default location

**"Executable not found"**
- Build the executable first: `build_windows.bat`

### Ubuntu/Debian

**"dpkg-deb not found"**
```bash
sudo apt-get install dpkg-dev
```

**"fakeroot not found"**
```bash
sudo apt-get install fakeroot
```

**Package installation fails**
```bash
sudo apt-get install -f  # Fix dependencies
```

## Advanced Usage

### Windows: Custom Installer Options

Edit `installers/windows/QdrantManager.iss`:

```iss
[Setup]
; Change default installation directory
DefaultDirName={autopf}\MyCustomName

; Add custom wizard pages
[Code]
procedure InitializeWizard();
begin
  // Custom initialization code
end;
```

### Ubuntu: Custom Package Options

Edit `installers/ubuntu/debian/control`:

```
Depends: ${shlibs:Depends}, ${misc:Depends}, python3 (>= 3.11), 
         custom-package (>= 1.0)
```

## CI/CD Integration

You can automate installer builds in CI/CD pipelines:

**GitHub Actions Example:**
```yaml
- name: Build Windows Installer
  run: |
    build_windows.bat
    cd installers
    build_windows_installer.bat

- name: Build Ubuntu Installer
  run: |
    ./build_linux.sh
    cd installers
    chmod +x build_ubuntu_installer.sh
    ./build_ubuntu_installer.sh
```

## Support

For issues or questions:
- Check `installers/README.md` for detailed documentation
- Review build logs for error messages
- Ensure all prerequisites are installed

