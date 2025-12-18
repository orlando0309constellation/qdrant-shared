#!/usr/bin/env python3
"""
Simple build script using PyInstaller directly (2025 best practice)
No spec file needed - uses command-line arguments
"""

import subprocess
import sys
import os
from pathlib import Path

def find_mysql_dlls():
    """Find MySQL connector DLL files to include in the build."""
    try:
        import mysql.connector
        mysql_base = Path(mysql.connector.__file__).parent.parent
        # Look for DLL files in mysql vendor/plugin directory
        vendor_plugin = mysql_base / 'vendor' / 'plugin'
        dlls = []
        if vendor_plugin.exists():
            dlls = list(vendor_plugin.glob('*.dll'))
            if sys.platform.startswith('linux'):
                dlls.extend(vendor_plugin.glob('*.so'))
        # Also include vendor DLLs (libcrypto, libssl, etc.)
        vendor_dir = mysql_base / 'vendor'
        if vendor_dir.exists():
            dlls.extend(vendor_dir.glob('*.dll'))
            if sys.platform.startswith('linux'):
                dlls.extend(vendor_dir.glob('*.so'))
        return dlls
    except ImportError:
        return []

def main():
    """Build executable using PyInstaller with direct command-line arguments."""
    
    # Get project root
    project_root = Path(__file__).parent.resolve()
    os.chdir(project_root)
    
    # Launcher script
    launcher = project_root / 'qdrant_distributed' / 'interface' / 'launcher.py'
    
    if not launcher.exists():
        print(f"ERROR: Launcher not found at {launcher}")
        sys.exit(1)
    
    # Icon path (Windows uses .ico, Linux can use PNG but PyInstaller handles it differently)
    icon_path = project_root / 'qdrant_distributed' / 'interface' / 'image' / 'qdrant-icon-seeklogo.png'
    # Windows can use PNG directly, Linux typically needs .ico or .png converted
    if sys.platform == 'win32' and icon_path.exists():
        icon_arg = f'--icon={icon_path}'
    elif sys.platform.startswith('linux') and icon_path.exists():
        # Linux can use PNG but it's less common, try it anyway
        icon_arg = f'--icon={icon_path}'
    else:
        icon_arg = ''
    
    # Find MySQL DLL files
    mysql_dlls = find_mysql_dlls()
    if mysql_dlls:
        print(f"Found {len(mysql_dlls)} MySQL DLL files to include")
    
    # Build command
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=QdrantManager',
        '--onefile',
        '--windowed',  # No console window for GUI
        '--clean',
        '--noconfirm',
        
        # Add data files
        '--add-data', f'{icon_path.parent}{os.pathsep}qdrant_distributed/interface/image',
        
        # Collect MySQL connector - includes all submodules, data files, and binaries
        '--collect-all=mysql.connector',
        
        # Additional hook path for custom hooks
        '--additional-hooks-dir=.',
    ]
    
    # Add MySQL DLL files if found
    for dll in mysql_dlls:
        # Add DLL to binaries - preserve directory structure
        # For onefile mode, DLLs are extracted to temp directory
        # Use relative path to preserve mysql/vendor/plugin structure
        if 'vendor' in str(dll) and 'plugin' in str(dll):
            target = 'mysql/vendor/plugin'
        elif 'vendor' in str(dll):
            target = 'mysql/vendor'
        else:
            target = '.'
        cmd.extend(['--add-binary', f'{dll}{os.pathsep}{target}'])
    
    # Hidden imports
    cmd.extend([
        '--hidden-import=tkinter',
        '--hidden-import=tkinter.ttk',
        '--hidden-import=tkinter.scrolledtext',
        '--hidden-import=tkinter.messagebox',
        '--hidden-import=tkinter.filedialog',
        '--hidden-import=dotenv',
        '--hidden-import=qdrant_client',
        '--hidden-import=qdrant_client.async_qdrant_client',
        '--hidden-import=mysql',
        '--hidden-import=mysql.connector',
        '--hidden-import=mysql.connector.cursor',
        '--hidden-import=mysql.connector.pooling',
        '--hidden-import=mysql.connector.plugins',
        '--hidden-import=mysql.connector.plugins.mysql_native_password',
        '--hidden-import=mysql.connector.plugins.caching_sha2_password',
        '--collect-submodules=mysql.connector',
        '--hidden-import=pymongo',
        '--hidden-import=numpy',
        '--hidden-import=numpy.core',
        '--hidden-import=numpy.core._multiarray_umath',
        
        # Exclude unnecessary modules (but keep numpy as it's required by qdrant_client)
        '--exclude-module=matplotlib',
        '--exclude-module=pandas',
        '--exclude-module=scipy',
        '--exclude-module=IPython',
        '--exclude-module=jupyter',
        '--exclude-module=pytest',
    ])
    
    # Add icon if available
    if icon_arg:
        cmd.append(icon_arg)
    
    # Add launcher script
    cmd.append(str(launcher))
    
    # Remove empty strings
    cmd = [c for c in cmd if c]
    
    print("=" * 60)
    print("Building Qdrant Manager Executable")
    print("=" * 60)
    print(f"Working directory: {project_root}")
    print(f"Launcher: {launcher}")
    if mysql_dlls:
        print(f"MySQL DLLs: {len(mysql_dlls)} files")
    print()
    print("Running PyInstaller...")
    print()
    
    try:
        result = subprocess.run(cmd, check=True, cwd=project_root)
        print()
        print("=" * 60)
        print("✅ Build completed successfully!")
        print("=" * 60)
        
        exe_name = 'QdrantManager.exe' if sys.platform == 'win32' else 'QdrantManager'
        exe_path = project_root / 'dist' / exe_name
        
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"Executable: {exe_path}")
            print(f"Size: {size_mb:.1f} MB")
        else:
            print(f"WARNING: Executable not found at {exe_path}")
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 60)
        print("❌ Build failed!")
        print("=" * 60)
        print(f"Error: {e}")
        return 1
    except FileNotFoundError:
        print()
        print("=" * 60)
        print("❌ PyInstaller not found!")
        print("=" * 60)
        print("Install it with: pip install pyinstaller")
        return 1

if __name__ == '__main__':
    sys.exit(main())
