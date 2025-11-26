"""
Status Bar Widget - Displays application status.
"""

import tkinter as tk
from tkinter import ttk


class StatusBar(ttk.Label):
    """Status bar widget for displaying application status."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="Ready", relief=tk.SUNKEN, anchor=tk.W, padding=5, **kwargs)
        self.pack(side=tk.BOTTOM, fill=tk.X)
    
    def set_text(self, text: str):
        """Update status text."""
        self.config(text=text)

