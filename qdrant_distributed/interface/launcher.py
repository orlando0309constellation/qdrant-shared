#!/usr/bin/env python
"""
Launcher script for Qdrant Manager Desktop Application
"""

import sys
import multiprocessing
import tkinter as tk
from qdrant_distributed.interface.app import QdrantManagerApp


def main():
    """Launch the desktop application."""
    # Required for multiprocessing in built applications (PyInstaller, etc.)
    if sys.platform == 'win32':
        multiprocessing.freeze_support()
    
    try:
        root = tk.Tk()
        app = QdrantManagerApp(root)
        root.mainloop()
        return 0
    except KeyboardInterrupt:
        print("\nApplication closed by user")
        return 0
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

