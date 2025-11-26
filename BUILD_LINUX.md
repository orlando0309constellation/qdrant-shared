# Building Linux Executable

## Quick Start

### Option 1: Using the build script (Recommended)
```bash
chmod +x build_linux.sh
./build_linux.sh
```

### Option 2: Direct Python script
```bash
python3 build_simple.py
```

## Requirements

1. **Python 3.11+** installed
2. **tkinter** for GUI:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install python3-tk
   
   # Fedora/RHEL
   sudo dnf install python3-tkinter
   
   # Arch Linux
   sudo pacman -S tk
   ```

3. **Dependencies**:
   ```bash
   pip3 install -e ".[all-db]"
   pip3 install pyinstaller
   ```

## Building on Linux

The executable will be created at: `dist/QdrantManager`

Make it executable:
```bash
chmod +x dist/QdrantManager
```

## Cross-Platform Building

**You cannot build a Linux executable on Windows directly.** You have several options:

### Option 1: Build on Linux Machine/VM
- Use a Linux machine, VM, or WSL2
- Run the build script there

### Option 2: Use Docker
```bash
# Create Dockerfile for building
docker run -it -v $(pwd):/app python:3.12 bash
cd /app
pip install -e ".[all-db]" pyinstaller
apt-get update && apt-get install -y python3-tk
python3 build_simple.py
```

### Option 3: Use WSL2 (Windows Subsystem for Linux)
```bash
# In WSL2
cd /mnt/d/projet/Official/qdrant-manager
./build_linux.sh
```

### Option 4: GitHub Actions CI/CD
Automate builds using GitHub Actions (see BUILD.md for example)

## Testing the Linux Executable

```bash
./dist/QdrantManager
```

## Troubleshooting

### "No module named '_tkinter'"
Install tkinter:
```bash
sudo apt-get install python3-tk  # Ubuntu/Debian
```

### "Permission denied"
Make executable:
```bash
chmod +x dist/QdrantManager
```

### Missing dependencies
Ensure all dependencies are installed:
```bash
pip3 install -e ".[all-db]"
```

