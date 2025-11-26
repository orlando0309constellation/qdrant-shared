"""
Progress Bar Widget - Displays operation progress with enhanced features.
"""

import tkinter as tk
from tkinter import ttk


class ProgressBar:
    """Enhanced progress bar widget with percentage display and status text."""
    
    def __init__(self, parent, before_widget=None):
        self.parent = parent
        self.before_widget = before_widget
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="")
        self._visible = False
        
        # Create container frame
        self.container = ttk.Frame(parent)
        
        # Status label (above progress bar)
        self.status_label = ttk.Label(self.container, textvariable=self.status_var, 
                                      font=("Segoe UI", 9), foreground="#666666")
        self.status_label.pack(anchor=tk.W, pady=(0, 4))
        
        # Progress bar frame with percentage
        progress_frame = ttk.Frame(self.container)
        progress_frame.pack(fill=tk.X)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                            maximum=100, mode='determinate',
                                            length=400)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        
        # Percentage label
        self.percentage_label = ttk.Label(progress_frame, text="0%", 
                                          font=("Segoe UI", 9, "bold"),
                                          width=5, anchor=tk.E)
        self.percentage_label.pack(side=tk.RIGHT)
        
        # Configure style for better appearance
        self._configure_style()
    
    def _configure_style(self):
        """Configure progress bar style for better appearance."""
        style = ttk.Style()
        style.configure("TProgressbar",
                       background="#007ACC",
                       troughcolor="#E1E4E8",
                       borderwidth=0,
                       lightcolor="#007ACC",
                       darkcolor="#007ACC")
        style.map("TProgressbar",
                 background=[("active", "#0098FF")])
    
    def show(self, status: str = ""):
        """Show the progress bar with optional status text."""
        if not self._visible:
            if self.before_widget is not None:
                self.container.pack(fill=tk.X, pady=(5, 10), before=self.before_widget)
            else:
                self.container.pack(fill=tk.X, pady=(5, 10))
            self._visible = True
        
        if status:
            self.set_status(status)
    
    def hide(self):
        """Hide the progress bar."""
        if self._visible:
            self.container.pack_forget()
            self._visible = False
            self.status_var.set("")
            self.progress_var.set(0)
            self.percentage_label.config(text="0%")
    
    def update(self, value: float, maximum: float = 100.0, status: str = None):
        """Update progress value and optionally status text."""
        percentage = min(100.0, max(0.0, (value / maximum) * 100))
        self.progress_var.set(percentage)
        self.percentage_label.config(text=f"{int(percentage)}%")
        
        if status is not None:
            self.set_status(status)
    
    def set_status(self, status: str):
        """Set status text displayed above the progress bar."""
        self.status_var.set(status)
    
    def reset(self):
        """Reset progress bar to 0."""
        self.progress_var.set(0)
        self.percentage_label.config(text="0%")
        self.status_var.set("")

