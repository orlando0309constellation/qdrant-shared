"""
Theme Manager - Handles application theming.
"""

import tkinter.ttk as ttk


class ThemeManager:
    """Manages application theme and styling."""
    
    def __init__(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._setup_default_theme()
    
    def _setup_default_theme(self):
        """Setup default theme configuration."""
        # Basic theme setup - can be extended later
        pass
    
    def get_style(self) -> ttk.Style:
        """Get the style object."""
        return self.style

