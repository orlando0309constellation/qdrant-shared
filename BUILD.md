# Building Executables for Qdrant Manager

This guide explains how to build standalone executables for Windows and Linux.

## Prerequisites

### For Windows:
- Python 3.11+ installed
- pip package manager
- Windows 10/11

### For Linux:
- Python 3.11+ installed
- pip package manager
- Linux distribution (Ubuntu, Debian, Fedora, etc.)

## Installation

1. **Install PyInstaller:**
   ```bash
   pip install pyinstaller
   ```

2. **Install project dependencies:**
   ```bash
   pip install -e ".[all-db]"
   ```

## Building Executables

### Windows

**Option 1: Using the batch script (Recommended)**
```cmd
build_windows.bat
```

**Option 2: Manual build**
```cmd
pyinstaller build.spec --clean --noconfirm
```

The executable will be created at: `dist\QdrantManager.exe`

### Linux

**Option 1: Using the shell script (Recommended)**
```bash
chmod +x build_linux.sh
./build_linux.sh
```

**Option 2: Manual build**
```bash
pyinstaller build.spec --clean --noconfirm
chmod +x dist/QdrantManager
```

The executable will be created at: `dist/QdrantManager`

## Build Options

### Debug Mode

To build with console window for debugging, edit `build.spec` and change:
```python
console=False,  # Change to True for debugging
```

### Single File vs Directory

The current spec file creates a single executable file. To create a directory distribution (faster startup), modify the `EXE` section in `build.spec`:

```python
exe = EXE(
    # ... existing options ...
    onefile=False,  # Change to False for directory distribution
)
```

### Icon

The icon is automatically included from `qdrant_distributed/interface/image/qdrant-icon-seeklogo.png`.

For Windows, you can also use a `.ico` file:
```python
icon='path/to/icon.ico'
```

## Distribution

### Windows
- The `QdrantManager.exe` file is standalone and can be distributed
- Users don't need Python installed
- All dependencies are bundled

### Linux
- The `QdrantManager` binary is standalone
- Users don't need Python installed
- All dependencies are bundled
- Make sure to set executable permissions: `chmod +x QdrantManager`

## Troubleshooting

### Missing Modules
If you encounter "ModuleNotFoundError" at runtime:

1. Add the missing module to `hiddenimports` in `build.spec`
2. Rebuild the executable

### Large Executable Size
The executable includes all Python dependencies. To reduce size:

1. Use `--exclude-module` to exclude unused modules
2. Consider using `onefile=False` for directory distribution
3. Use UPX compression (already enabled in spec file)

### Antivirus False Positives
Some antivirus software may flag PyInstaller executables. This is a known issue. Solutions:

1. Submit the executable to your antivirus vendor for whitelisting
2. Code sign the executable (Windows)
3. Use directory distribution instead of single file

### Linux: "No module named '_tkinter'"
If you get this error on Linux, install tkinter:
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch Linux
sudo pacman -S tk
```

## Advanced Configuration

### Custom Build Options

Edit `build.spec` to customize:

- **Application name**: Change `name=app_name`
- **Version info**: Add version information (Windows)
- **UPX compression**: Enable/disable with `upx=True/False`
- **Console window**: Control with `console=True/False`

### Version Information (Windows)

To add version information to the Windows executable, create a version file and reference it in the spec:

```python
exe = EXE(
    # ... existing options ...
    version='version_info.txt',
)
```

## Cross-Platform Building

**Note:** You cannot build Windows executables on Linux or vice versa directly. You need to:

1. Build on the target platform, OR
2. Use Docker/VM with the target OS, OR
3. Use CI/CD services (GitHub Actions, etc.)

## CI/CD Example (GitHub Actions)

You can automate builds using GitHub Actions. Example workflow:

```yaml
name: Build Executables

on:
  release:
    types: [created]

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install pyinstaller
      - run: pip install -e ".[all-db]"
      - run: pyinstaller build.spec --clean --noconfirm
      - uses: actions/upload-artifact@v3
        with:
          name: windows-executable
          path: dist/QdrantManager.exe

  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: sudo apt-get install -y python3-tk
      - run: pip install pyinstaller
      - run: pip install -e ".[all-db]"
      - run: pyinstaller build.spec --clean --noconfirm
      - run: chmod +x dist/QdrantManager
      - uses: actions/upload-artifact@v3
        with:
          name: linux-executable
          path: dist/QdrantManager
```

## Testing the Executable

After building, test the executable:

1. **Windows**: Double-click `QdrantManager.exe` or run from command prompt
2. **Linux**: Run `./dist/QdrantManager` from terminal

Make sure to test all features:
- Configuration dialog
- List shards operation
- Move/Replicate operations
- MySQL connection
- Qdrant connection

