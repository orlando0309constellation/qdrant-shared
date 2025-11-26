"""
Qdrant Manager Desktop Application - Refactored with MVC pattern.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, List
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from qdrant_distributed.constant import SHARED_COLLECTION_NAME
from qdrant_distributed.models.shard import ShardInfo

# Import refactored components
from qdrant_distributed.interface.services.app_state import AppState
from qdrant_distributed.interface.services.theme_manager import ThemeManager
from qdrant_distributed.interface.controllers.service_controller import ServiceController
from qdrant_distributed.interface.controllers.validation_controller import ValidationController
from qdrant_distributed.interface.controllers.operation_controller import OperationController
from qdrant_distributed.interface.views.config_dialog import ConfigDialog
from qdrant_distributed.interface.views.control_panel import ControlPanel
from qdrant_distributed.interface.views.output_panel import OutputPanel
from qdrant_distributed.interface.widgets.status_bar import StatusBar


class QdrantManagerApp:
    """Desktop GUI application for Qdrant cluster management - Refactored."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Qdrant Cluster Manager")
        self.root.geometry("1200x850")
        
        # Set window icon
        self._set_window_icon()
        
        # Initialize services
        self.theme_manager = ThemeManager()
        self.app_state = AppState()
        self.service_controller = ServiceController()
        self.validation_controller = ValidationController(self.app_state)
        self.operation_controller = OperationController(
            self.app_state,
            self.service_controller,
            self.validation_controller
        )
        
        # Setup UI
        self.setup_menu()
        self.setup_ui()
        self._connect_controllers()
    
    def setup_menu(self):
        """Setup the menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        config_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configuration", menu=config_menu)
        config_menu.add_command(label="Settings...", command=self.open_config_dialog)
    
    def open_config_dialog(self):
        """Open the configuration dialog."""
        ConfigDialog(self.root, self.app_state, self.service_controller)
    
    def setup_ui(self):
        """Setup the main user interface."""
        # Main container
        main_container = ttk.Frame(self.root, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = ttk.Label(header_frame, text="🔧 Qdrant Cluster Manager", 
                               font=("Segoe UI", 18, "bold"))
        title_label.pack(side=tk.LEFT)
        
        # Create two-column layout
        content_paned = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        content_paned.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Left Panel - Controls
        left_panel = ttk.Frame(content_paned, padding="10")
        content_paned.add(left_panel, weight=1)
        
        # Right Panel - Output
        right_panel = ttk.Frame(content_paned, padding="10")
        content_paned.add(right_panel, weight=2)
        
        # Create views
        self.control_panel = ControlPanel(left_panel, self.app_state, self.operation_controller)
        self.output_panel = OutputPanel(right_panel, self.app_state)
        
        # Status Bar
        self.status_bar = StatusBar(self.root)
    
    def _set_window_icon(self):
        """Set the window icon from the image file."""
        try:
            # Get the path to the icon file
            icon_path = Path(__file__).parent / "image" / "qdrant-icon-seeklogo.png"
            
            if icon_path.exists():
                # Try using iconphoto for PNG (works on all platforms)
                try:
                    icon_image = tk.PhotoImage(file=str(icon_path))
                    self.root.iconphoto(True, icon_image)
                    # Keep a reference to prevent garbage collection
                    self._icon_image = icon_image
                except Exception:
                    # Fallback: try iconbitmap for Windows
                    try:
                        self.root.iconbitmap(str(icon_path))
                    except Exception:
                        # If both fail, silently continue without icon
                        pass
        except Exception:
            # If icon setting fails, continue without it
            pass
    
    def _connect_controllers(self):
        """Connect controller events to UI updates."""
        # Operation controller callbacks
        self.operation_controller.register_callback("operation_start", self._on_operation_start)
        self.operation_controller.register_callback("operation_complete", self._on_operation_complete)
        self.operation_controller.register_callback("progress_update", self._on_progress_update)
        self.operation_controller.register_callback("log_output", self._on_log_output)
        self.operation_controller.register_callback("status_update", self._on_status_update)
        self.operation_controller.register_callback("display_shards", self._on_display_shards)
        self.operation_controller.register_callback("error", self._on_error)
        self.operation_controller.register_callback("get_selected_shards", self._get_selected_shards)
    
    def _on_operation_start(self):
        """Handle operation start event."""
        self.control_panel.set_execute_button_state(tk.DISABLED)
        self.output_panel.progress_bar.show("Initializing operation...")
        self.status_bar.set_text("Operation in progress...")
    
    def _on_operation_complete(self):
        """Handle operation complete event."""
        self.control_panel.set_execute_button_state(tk.NORMAL)
        self.output_panel.progress_bar.update(100, status="Operation completed!")
        # Hide after a brief delay to show completion
        self.root.after(500, self.output_panel.progress_bar.hide)
    
    def _on_progress_update(self, value: float, status: str = None):
        """Handle progress update event."""
        self.output_panel.progress_bar.update(value, status=status)
    
    def _on_log_output(self, text: str, tag: str = None):
        """Handle log output event."""
        self.output_panel.log_viewer.log(text, tag)
    
    def _on_status_update(self, text: str):
        """Handle status update event."""
        self.status_bar.set_text(text)
    
    def _on_display_shards(self, peer_shards: Dict[int, List[ShardInfo]], peer_uris: Dict[int, str]):
        """Handle display shards event."""
        self.app_state.current_peer_shards = peer_shards
        self.app_state.current_peer_uris = peer_uris
        self.output_panel.display_shards(peer_shards, peer_uris)
    
    def _on_error(self, error_msg: str):
        """Handle error event."""
        messagebox.showerror("Operation Failed", error_msg)
    
    def _get_selected_shards(self, from_peer: int) -> List[int]:
        """Get selected shard IDs from treeview."""
        result = self.output_panel.shard_tree.get_selected_shard_ids(from_peer)
        return result if result else []

