"""
Log Viewer Widget - Displays application logs.
"""

import tkinter as tk
from tkinter import scrolledtext


class LogViewer(scrolledtext.ScrolledText):
    """Log viewer widget for displaying application logs."""
    
    def __init__(self, parent, **kwargs):
        default_kwargs = {
            'wrap': tk.WORD,
            'font': ("Consolas", 10),
            'bg': "#1e1e1e",
            'fg': "#d4d4d4",
            'insertbackground': "#ffffff"
        }
        default_kwargs.update(kwargs)
        super().__init__(parent, **default_kwargs)
        self._setup_tags()
    
    def _setup_tags(self):
        """Setup text tags for formatting."""
        self.tag_config("header", foreground="#4ec9b0", font=("Consolas", 10, "bold"))
        self.tag_config("success", foreground="#4ec9b0")
        self.tag_config("error", foreground="#f48771")
        self.tag_config("warning", foreground="#dcdcaa")
        self.tag_config("info", foreground="#569cd6")
    
    def log(self, text: str, tag: str = None):
        """Add log entry."""
        self.insert(tk.END, text + "\n", tag)
        self.see(tk.END)
    
    def clear(self):
        """Clear all logs."""
        self.delete(1.0, tk.END)

