"""
Migration Dialog View - Dialog window for Qdrant migration operations.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from qdrant_client import QdrantClient
import mysql.connector

from qdrant_distributed.interface.controllers.migration_controller import MigrationController
from qdrant_distributed.interface.widgets.progress_bar import ProgressBar
from qdrant_distributed.interface.widgets.log_viewer import LogViewer
from qdrant_distributed.services.config_service import ConfigService
from qdrant_distributed.config import (
    get_qdrant_url, get_qdrant_port, get_qdrant_api_key, get_qdrant_https,
    get_mysql_host, get_mysql_port, get_mysql_user, get_mysql_password, get_mysql_database
)
import os


class MigrationResultsDialog:
    """Separate dialog window for migration results and logs."""
    
    def __init__(self, parent, migration_controller: MigrationController):
        self.parent = parent
        self.migration_controller = migration_controller
        self._is_closing = False
        
        # Timer-related variables
        self._start_time = None
        self._timer_running = False
        self._timer_job = None
        
        self.window = tk.Toplevel(parent)
        self.window.title("Migration Results & Logs")
        self.window.geometry("800x500")
        self.window.minsize(700, 400)
        self.window.resizable(True, True)
        self.window.transient(parent)
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self._center_window()
        self._setup_ui()
        self._connect_controller()
    
    def _center_window(self):
        """Center the window on screen."""
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (self.window.winfo_width() // 2)
        y = (self.window.winfo_screenheight() // 2) - (self.window.winfo_height() // 2)
        self.window.geometry(f"+{x}+{y}")
    
    def _setup_ui(self):
        """Setup the results dialog UI."""
        main_frame = ttk.Frame(self.window, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header frame with title and elapsed time
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Title on the left
        title_label = ttk.Label(header_frame, text="📊 Migration Results & Logs", 
                               font=("Segoe UI", 12, "bold"))
        title_label.pack(side=tk.LEFT)
        
        # Elapsed time on the right
        self._elapsed_frame = ttk.Frame(header_frame)
        self._elapsed_frame.pack(side=tk.RIGHT)
        
        ttk.Label(self._elapsed_frame, text="⏱️", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 3))
        self._elapsed_label = ttk.Label(self._elapsed_frame, text="00:00:00", 
                                        font=("Consolas", 11, "bold"), foreground="#2196F3")
        self._elapsed_label.pack(side=tk.LEFT)
        self._elapsed_status = ttk.Label(self._elapsed_frame, text="", 
                                         font=("Segoe UI", 9), foreground="gray")
        self._elapsed_status.pack(side=tk.LEFT, padx=(8, 0))
        
        output_frame = ttk.LabelFrame(main_frame, text="Output & Logs", padding="5")
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        # Progress bar
        self.progress_bar = ProgressBar(output_frame)
        
        # Create notebook for Results and Logs tabs
        output_notebook = ttk.Notebook(output_frame)
        output_notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Tab 1: Results
        results_tab = ttk.Frame(output_notebook, padding="5")
        output_notebook.add(results_tab, text="📊 Results")
        
        # Results table frame
        results_table_frame = ttk.Frame(results_tab)
        results_table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars for table
        table_scroll_y = ttk.Scrollbar(results_table_frame, orient=tk.VERTICAL)
        table_scroll_x = ttk.Scrollbar(results_table_frame, orient=tk.HORIZONTAL)
        
        # Create treeview for migration results
        columns = ("Collection ID", "Status", "Missing", "Migrated", "Total", "Progress", "State")
        self.results_tree = ttk.Treeview(results_table_frame, columns=columns, show="headings",
                                        yscrollcommand=table_scroll_y.set,
                                        xscrollcommand=table_scroll_x.set)
        
        # Configure columns
        self.results_tree.heading("Collection ID", text="Collection ID")
        self.results_tree.heading("Status", text="Status")
        self.results_tree.heading("Missing", text="Missing")
        self.results_tree.heading("Migrated", text="Migrated")
        self.results_tree.heading("Total", text="Total")
        self.results_tree.heading("Progress", text="Progress")
        self.results_tree.heading("State", text="State")
        
        # Set column widths
        self.results_tree.column("Collection ID", width=200, anchor=tk.W)
        self.results_tree.column("Status", width=100, anchor=tk.CENTER)
        self.results_tree.column("Missing", width=80, anchor=tk.E)
        self.results_tree.column("Migrated", width=80, anchor=tk.E)
        self.results_tree.column("Total", width=80, anchor=tk.E)
        self.results_tree.column("Progress", width=150, anchor=tk.CENTER)
        self.results_tree.column("State", width=200, anchor=tk.W)
        
        # Dictionary to store progress bars for each row
        self.progress_bars = {}  # {item_id: (progress_bar, progress_var)}
        
        # Bind events to update progress bar positions
        self.results_tree.bind("<Configure>", self._update_progress_bar_positions)
        self.results_tree.bind("<Button-1>", self._update_progress_bar_positions)
        table_scroll_y.config(command=lambda *args: (self.results_tree.yview(*args), self._update_progress_bar_positions()))
        self.results_tree.config(yscrollcommand=lambda *args: (table_scroll_y.set(*args), self._update_progress_bar_positions()))
        
        # Configure tags for styling
        self.results_tree.tag_configure("processing", background="#e3f2fd", foreground="#000000")
        self.results_tree.tag_configure("completed", background="#e8f5e9", foreground="#000000")
        self.results_tree.tag_configure("failed", background="#ffebee", foreground="#000000")
        self.results_tree.tag_configure("disabled", background="#f5f5f5", foreground="#9e9e9e")
        
        # Configure scrollbars with progress bar position updates
        def yview_with_update(*args):
            self.results_tree.yview(*args)
            self.window.after_idle(self._update_progress_bar_positions)
        
        table_scroll_y.config(command=yview_with_update)
        self.results_tree.config(yscrollcommand=lambda *args: (table_scroll_y.set(*args), self.window.after_idle(self._update_progress_bar_positions)))
        table_scroll_x.config(command=self.results_tree.xview)
        
        # Grid layout for table and scrollbars
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        table_scroll_y.grid(row=0, column=1, sticky="ns")
        table_scroll_x.grid(row=1, column=0, sticky="ew")
        results_table_frame.grid_rowconfigure(0, weight=1)
        results_table_frame.grid_columnconfigure(0, weight=1)
        
        # Store collection items for updates
        self.collection_items = {}  # collection_id -> tree item id
        self.current_processing_collection = None  # Track which collection is currently processing
        self.collection_batch_info = {}  # collection_id -> {'total_batches': int, 'current_batch': int}
        
        # Tab 2: Logs
        logs_tab = ttk.Frame(output_notebook, padding="5")
        output_notebook.add(logs_tab, text="📝 Logs")
        
        # Log viewer
        self.log_viewer = LogViewer(logs_tab)
        self.log_viewer.pack(fill=tk.BOTH, expand=True)
    
    def _connect_controller(self):
        """Connect controller events to UI updates."""
        self.migration_controller.register_callback("migration_start", self._on_migration_start)
        self.migration_controller.register_callback("migration_complete", self._on_migration_complete)
        self.migration_controller.register_callback("progress_update", self._on_progress_update)
        self.migration_controller.register_callback("log_output", self._on_log_output)
        self.migration_controller.register_callback("status_update", self._on_status_update)
        self.migration_controller.register_callback("error", self._on_error)
        self.migration_controller.register_callback("collection_status", self._on_collection_status)
    
    def _on_migration_start(self):
        """Handle migration start event."""
        if not self._is_closing and self.window.winfo_exists():
            try:
                self.progress_bar.show("Initializing migration...")
                self.log_viewer.clear()
                # Clear results table
                for item in self.results_tree.get_children():
                    self.results_tree.delete(item)
                # Clean up progress bars
                for item_id, (progress_bar, _) in self.progress_bars.items():
                    try:
                        progress_bar.destroy()
                    except:
                        pass
                self.progress_bars.clear()
                self.collection_items.clear()
                self.collection_batch_info.clear()
                self.current_processing_collection = None
                
                # Start elapsed time timer
                self._start_timer()
            except tk.TclError:
                pass
    
    def _on_migration_complete(self):
        """Handle migration complete event."""
        if not self._is_closing and self.window.winfo_exists():
            try:
                self.progress_bar.update(100, status="Migration completed!")
                self.window.after(500, self.progress_bar.hide)
                
                # Stop elapsed time timer and show final time
                self._stop_timer(completed=True)
            except tk.TclError:
                pass
    
    def _on_progress_update(self, value: float, status: str = None):
        """Handle progress update event."""
        if not self._is_closing and self.window.winfo_exists():
            try:
                self.progress_bar.update(value, status=status)
            except tk.TclError:
                pass
    
    def _on_log_output(self, text: str, tag: str = None):
        """Handle log output event."""
        if not self._is_closing and self.window.winfo_exists():
            try:
                self.log_viewer.log(text, tag)
            except tk.TclError:
                pass
    
    def _on_status_update(self, text: str):
        """Handle status update event."""
        pass
    
    def _on_error(self, error_msg: str):
        """Handle error event."""
        if not self._is_closing and self.window.winfo_exists():
            messagebox.showerror("Migration Failed", error_msg, parent=self.window)
    
    def _on_collection_status(self, collection_id: str, status: str, missing: int = 0,
                             migrated: int = 0, total: int = 0, current_batch: int = 0,
                             state: str = "", total_batches: int = 0):
        """Handle collection status update event."""
        if not self._is_closing and self.window.winfo_exists():
            self._update_collection_status(collection_id, status, missing, migrated, total, current_batch, state, total_batches)
    
    def _update_collection_status(self, collection_id: str, status: str = "Processing", 
                                 missing: int = 0, migrated: int = 0, total: int = 0,
                                 current_batch: int = 0, state: str = "", total_batches: int = 0):
        """Update or create collection status in results table."""
        if self._is_closing or not self.window.winfo_exists():
            return
        
        # Skip "Skipped" collections
        if status == "Skipped":
            if collection_id in self.collection_items:
                item_id = self.collection_items[collection_id]
                try:
                    self.results_tree.delete(item_id)
                    del self.collection_items[collection_id]
                    if collection_id in self.collection_batch_info:
                        del self.collection_batch_info[collection_id]
                except tk.TclError:
                    pass
            return
        
        try:
            # Store batch info - use the values directly from the callback
            if total_batches > 0:
                self.collection_batch_info[collection_id] = {'total_batches': total_batches, 'current_batch': current_batch}
            
            # Calculate progress percentage - use parameters directly, fallback to stored info
            progress_pct = 0
            use_total_batches = total_batches if total_batches > 0 else self.collection_batch_info.get(collection_id, {}).get('total_batches', 0)
            use_current_batch = current_batch if total_batches > 0 else self.collection_batch_info.get(collection_id, {}).get('current_batch', 0)
            
            if use_total_batches > 0:
                progress_pct = int(((use_current_batch + 1) / use_total_batches) * 100)
                progress_pct = min(100, max(0, progress_pct))
            elif total > 0 and migrated > 0:
                progress_pct = min(100, int((migrated / total) * 100))
            elif status in ["Completed", "Synced"]:
                progress_pct = 100
            elif status == "Failed":
                progress_pct = 0
            
            # Create progress text for display (fallback if progress bar fails)
            if use_total_batches > 0:
                progress_text = f"{progress_pct}% ({use_current_batch + 1}/{use_total_batches})"
            elif total > 0:
                progress_text = f"{progress_pct}% ({migrated}/{total})"
            elif status == "Failed":
                progress_text = "Failed"
            elif status == "Pending":
                progress_text = "Pending"
            else:
                progress_text = f"{progress_pct}%"
            
            # Update current processing collection
            if status == "Processing" or status == "Starting":
                self.current_processing_collection = collection_id
            elif status in ["Completed", "Failed", "Synced", "Skipped"]:
                if self.current_processing_collection == collection_id:
                    self.current_processing_collection = None
            
            if collection_id not in self.collection_items:
                # Create new item
                item_id = self.results_tree.insert("", tk.END, values=(
                    collection_id, status, missing, migrated, total, "", state
                ))
                self.collection_items[collection_id] = item_id
                
                # Create progress bar for this row
                progress_var = tk.DoubleVar(value=float(progress_pct))
                progress_bar = ttk.Progressbar(
                    self.results_tree,
                    variable=progress_var,
                    maximum=100.0,
                    mode='determinate',
                    length=130,
                    style="TProgressbar"
                )
                self.progress_bars[item_id] = (progress_bar, progress_var)
                progress_var.set(float(progress_pct))
                self._update_progress_bar_position(item_id)
            else:
                # Update existing item
                item_id = self.collection_items[collection_id]
                current_values = list(self.results_tree.item(item_id, "values"))
                if len(current_values) < 7:
                    current_values = [collection_id, status, missing, migrated, total, progress_text, state]
                else:
                    current_values[1] = "✅ Completed" if status == "Completed" else ("❌ Failed" if status == "Failed" else ("✅ Synced" if status == "Synced" else ("⏭️ Skipped" if status == "Skipped" else "🔄 Processing")))
                    current_values[2] = missing
                    current_values[3] = migrated
                    current_values[4] = total
                    current_values[5] = ""
                    current_values[6] = state
                self.results_tree.item(item_id, values=current_values)
                
                # Update progress bar value
                if item_id in self.progress_bars:
                    progress_bar, progress_var = self.progress_bars[item_id]
                    progress_var.set(float(progress_pct))
                    progress_bar.update_idletasks()
                    self._update_progress_bar_position(item_id)
            
            # Apply tags based on status
            tags = []
            if collection_id == self.current_processing_collection:
                tags.append("processing")
            elif status == "Completed" or status == "Synced":
                tags.append("completed")
            elif status == "Failed":
                tags.append("failed")
            elif collection_id != self.current_processing_collection and self.current_processing_collection is not None:
                tags.append("disabled")
            
            if tags:
                self.results_tree.item(item_id, tags=tags)
            
            # Scroll to show the updated item
            self.results_tree.see(item_id)
            self.window.after_idle(self._update_progress_bar_position, item_id)
        except tk.TclError:
            pass
    
    def _update_progress_bar_position(self, item_id):
        """Update the position of a single progress bar."""
        if self._is_closing or not self.window.winfo_exists():
            return
        
        if item_id not in self.progress_bars:
            return
        
        try:
            progress_bar, _ = self.progress_bars[item_id]
            bbox = self.results_tree.bbox(item_id, "Progress")
            if bbox:
                x, y, width, height = bbox
                progress_bar.place(x=x + 2, y=y + 2, width=width - 4, height=height - 4)
            else:
                progress_bar.place_forget()
        except tk.TclError:
            pass
    
    def _update_progress_bar_positions(self, event=None):
        """Update positions of all progress bars."""
        if self._is_closing or not self.window.winfo_exists():
            return
        
        try:
            for item_id in self.progress_bars:
                self._update_progress_bar_position(item_id)
        except tk.TclError:
            pass
    
    # =========================================================================
    # Elapsed Time Timer
    # =========================================================================
    
    def _format_elapsed_time(self, seconds: float) -> str:
        """Format seconds into HH:MM:SS string."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _start_timer(self):
        """Start the elapsed time timer."""
        self._start_time = time.time()
        self._timer_running = True
        self._elapsed_status.config(text="Running...", foreground="#4CAF50")
        self._elapsed_label.config(foreground="#2196F3")
        self._update_elapsed_time()
    
    def _stop_timer(self, completed: bool = False):
        """Stop the elapsed time timer."""
        self._timer_running = False
        
        # Cancel scheduled update
        if self._timer_job:
            try:
                self.window.after_cancel(self._timer_job)
            except tk.TclError:
                pass
            self._timer_job = None
        
        # Update status label
        if self._start_time:
            elapsed = time.time() - self._start_time
            final_time = self._format_elapsed_time(elapsed)
            try:
                self._elapsed_label.config(text=final_time)
                if completed:
                    self._elapsed_status.config(text="✓ Completed", foreground="#4CAF50")
                    self._elapsed_label.config(foreground="#4CAF50")
                else:
                    self._elapsed_status.config(text="Stopped", foreground="#FF9800")
                    self._elapsed_label.config(foreground="#FF9800")
            except tk.TclError:
                pass
    
    def _update_elapsed_time(self):
        """Update the elapsed time display."""
        if not self._timer_running or self._is_closing:
            return
        
        try:
            if not self.window.winfo_exists():
                return
            
            if self._start_time:
                elapsed = time.time() - self._start_time
                time_str = self._format_elapsed_time(elapsed)
                self._elapsed_label.config(text=time_str)
            
            # Schedule next update (every 1 second)
            self._timer_job = self.window.after(1000, self._update_elapsed_time)
        except tk.TclError:
            self._timer_running = False
    
    def _on_close(self):
        """Handle window close event."""
        self._is_closing = True
        
        # Stop timer
        self._stop_timer(completed=False)
        
        # Cancel migration if running
        if self.migration_controller.is_running():
            from tkinter import messagebox
            if messagebox.askyesno(
                "Cancel Migration?", 
                "A migration is currently running. Do you want to cancel it?\n\n"
                "Note: The current operation may complete before cancellation takes effect.",
                parent=self.window
            ):
                self.migration_controller.cancel()
                # Close immediately - cancel() will emit migration_complete
                # which will re-enable the execute button in the main dialog
            else:
                # User chose not to cancel, so don't destroy window yet
                self._is_closing = False
                return
        
        self.window.destroy()


class MigrationDialog:
    """Migration dialog window with tabbed interface."""
    
    def __init__(self, parent):
        self.parent = parent
        self.migration_controller = MigrationController()
        self._is_closing = False
        
        self.window = tk.Toplevel(parent)
        self.window.title("Qdrant Migration")
        self.window.geometry("900x700")
        self.window.minsize(800, 600)
        self.window.resizable(True, True)
        self.window.transient(parent)
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Results dialog reference
        self.results_dialog = None
        
        self._center_window()
        self._setup_ui()
    
    def _center_window(self):
        """Center the window on screen."""
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (self.window.winfo_width() // 2)
        y = (self.window.winfo_screenheight() // 2) - (self.window.winfo_height() // 2)
        self.window.geometry(f"+{x}+{y}")
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="🔄 Qdrant Migration", 
                               font=("Segoe UI", 16, "bold"))
        title_label.pack(pady=(0, 15))
        
        # Create main notebook for Environment Variables, Database Configuration, and Migration Options tabs
        main_notebook = ttk.Notebook(main_frame)
        main_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Environment Variables
        env_tab = ttk.Frame(main_notebook, padding="10")
        main_notebook.add(env_tab, text="📝 Environment Variables")
        
        # Environment Variables Section
        env_frame = ttk.LabelFrame(env_tab, text="Environment Variables", padding="10")
        env_frame.pack(fill=tk.BOTH, expand=True)
        
        env_help = ttk.Label(env_frame, 
                            text="Paste environment variables below (KEY=VALUE format). Click 'Load Config' to populate all fields.",
                            font=("Segoe UI", 9))
        env_help.pack(anchor=tk.W, pady=(0, 5))
        
        # Text area for environment variables
        env_text_frame = ttk.Frame(env_frame)
        env_text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        env_scrollbar = ttk.Scrollbar(env_text_frame)
        env_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.env_text = tk.Text(env_text_frame, wrap=tk.WORD, 
                               font=("Consolas", 9),
                               yscrollcommand=env_scrollbar.set)
        self.env_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        env_scrollbar.config(command=self.env_text.yview)
        
        # Load Config button
        env_button_frame = ttk.Frame(env_frame)
        env_button_frame.pack(fill=tk.X)
        ttk.Button(env_button_frame, text="📥 Load Config from Environment Variables", 
                  command=self._load_config_from_env_text).pack(side=tk.LEFT)
        
        # Tab 2: Database Configuration
        db_config_tab = ttk.Frame(main_notebook, padding="10")
        main_notebook.add(db_config_tab, text="⚙️ Database Configuration")
        
        # Database Configuration Notebook
        db_notebook = ttk.Notebook(db_config_tab)
        db_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Default Qdrant Config (Source)
        source_tab = ttk.Frame(db_notebook, padding="15")
        db_notebook.add(source_tab, text="Default Qdrant (Source)")
        self._setup_qdrant_tab(source_tab, "source")
        
        # Tab 2: Target Qdrant Config
        target_tab = ttk.Frame(db_notebook, padding="15")
        db_notebook.add(target_tab, text="Target Qdrant")
        self._setup_qdrant_tab(target_tab, "target")
        
        # Tab 3: MySQL Source Config
        mysql_tab = ttk.Frame(db_notebook, padding="15")
        db_notebook.add(mysql_tab, text="MySQL Source")
        self._setup_mysql_tab(mysql_tab)
        
        # Tab 3: Migration Options
        options_tab = ttk.Frame(main_notebook, padding="15")
        main_notebook.add(options_tab, text="🚀 Migration Options")
        
        # Mode selection
        mode_frame = ttk.LabelFrame(options_tab, text="Migration Mode", padding="12")
        mode_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.mode_var = tk.StringVar(value="migrate")
        modes = [
            ("Migrate All", "migrate"),
            ("Migrate Missing Only", "migrate-usc"),
            ("Check Sync", "check")
        ]
        for text, value in modes:
            ttk.Radiobutton(mode_frame, text=text, variable=self.mode_var, 
                           value=value).pack(anchor=tk.W, pady=2)
        
        # Options checkboxes
        options_frame = ttk.LabelFrame(options_tab, text="Options", padding="12")
        options_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.reverse_var = tk.BooleanVar(value=False)
        self.https_var = tk.BooleanVar(value=get_qdrant_https(default=True))
        ttk.Checkbutton(options_frame, text="Reverse Migration", 
                       variable=self.reverse_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="Use HTTPS", 
                       variable=self.https_var).pack(anchor=tk.W, pady=2)
        
        # Execute Button
        button_frame = ttk.Frame(options_tab)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        self.execute_button = ttk.Button(button_frame, text="▶ Execute Migration", 
                                         command=self._execute_migration, width=25)
        self.execute_button.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self._on_close, width=15).pack(side=tk.RIGHT)
    
    def _setup_qdrant_tab(self, parent, tab_type: str):
        """Setup Qdrant configuration tab."""
        frame = ttk.LabelFrame(parent, text=f"{'Source' if tab_type == 'source' else 'Target'} Qdrant Connection Settings", 
                              padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Load default values
        if tab_type == "source":
            url = get_qdrant_url()
            port = get_qdrant_port()
            api_key = get_qdrant_api_key() or ""
            https = get_qdrant_https(default=True)
        else:
            # Target - load from env vars or use defaults
            url = os.getenv("QDRANT_URL_2", "localhost")
            port = os.getenv("QDRANT_PORT_2", "6333")
            api_key = os.getenv("QDRANT_API_KEY_2", os.getenv("QDRANT_API_KEY", ""))
            https = True
        
        # URL
        url_row = ttk.Frame(frame)
        url_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(url_row, text="URL:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        url_var = tk.StringVar(value=url)
        ttk.Entry(url_row, textvariable=url_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        setattr(self, f"{tab_type}_url_var", url_var)
        
        # Port
        port_row = ttk.Frame(frame)
        port_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(port_row, text="Port:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        port_var = tk.StringVar(value=str(port))
        ttk.Entry(port_row, textvariable=port_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        setattr(self, f"{tab_type}_port_var", port_var)
        
        # API Key
        api_key_row = ttk.Frame(frame)
        api_key_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(api_key_row, text="API Key:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        api_key_var = tk.StringVar(value=api_key)
        ttk.Entry(api_key_row, textvariable=api_key_var, width=40, show="*").pack(side=tk.LEFT, fill=tk.X, expand=True)
        setattr(self, f"{tab_type}_api_key_var", api_key_var)
        
        # HTTPS
        https_row = ttk.Frame(frame)
        https_row.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(https_row, text="Use HTTPS:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        https_var = tk.BooleanVar(value=https)
        ttk.Checkbutton(https_row, variable=https_var).pack(side=tk.LEFT)
        setattr(self, f"{tab_type}_https_var", https_var)
        
        # Test Connection Button
        test_frame = ttk.Frame(frame)
        test_frame.pack(fill=tk.X)
        ttk.Button(test_frame, text="Test Connection", 
                  command=lambda: self._test_qdrant_connection(tab_type)).pack(side=tk.LEFT)
    
    def _setup_mysql_tab(self, parent):
        """Setup MySQL configuration tab."""
        frame = ttk.LabelFrame(parent, text="MySQL Connection Settings", padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Use "ours" (default) option
        use_ours_frame = ttk.Frame(frame)
        use_ours_frame.pack(fill=tk.X, pady=(0, 15))
        self.mysql_use_ours_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(use_ours_frame, text="Use default MySQL configuration (ours)", 
                       variable=self.mysql_use_ours_var,
                       command=self._toggle_mysql_custom).pack(anchor=tk.W)
        
        # Custom MySQL config (initially disabled)
        custom_frame = ttk.LabelFrame(frame, text="Custom MySQL Configuration", padding="10")
        custom_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.mysql_custom_frame = custom_frame
        self.mysql_custom_enabled = False
        
        # Host
        host_row = ttk.Frame(custom_frame)
        host_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(host_row, text="Host:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        self.mysql_host_var = tk.StringVar(value=get_mysql_host())
        ttk.Entry(host_row, textvariable=self.mysql_host_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Port
        port_row = ttk.Frame(custom_frame)
        port_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(port_row, text="Port:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        self.mysql_port_var = tk.StringVar(value=str(get_mysql_port()))
        ttk.Entry(port_row, textvariable=self.mysql_port_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # User
        user_row = ttk.Frame(custom_frame)
        user_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(user_row, text="User:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        self.mysql_user_var = tk.StringVar(value=get_mysql_user())
        ttk.Entry(user_row, textvariable=self.mysql_user_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Password
        password_row = ttk.Frame(custom_frame)
        password_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(password_row, text="Password:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        self.mysql_password_var = tk.StringVar(value=get_mysql_password())
        ttk.Entry(password_row, textvariable=self.mysql_password_var, width=40, show="*").pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Database
        database_row = ttk.Frame(custom_frame)
        database_row.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(database_row, text="Database:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        self.mysql_database_var = tk.StringVar(value=get_mysql_database())
        ttk.Entry(database_row, textvariable=self.mysql_database_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Test Connection Button
        test_frame = ttk.Frame(frame)
        test_frame.pack(fill=tk.X)
        ttk.Button(test_frame, text="Test Connection", 
                  command=self._test_mysql_connection).pack(side=tk.LEFT)
        
        # Initially disable custom fields
        self._toggle_mysql_custom()
    
    def _toggle_mysql_custom(self):
        """Toggle MySQL custom configuration fields."""
        use_ours = self.mysql_use_ours_var.get()
        state = tk.DISABLED if use_ours else tk.NORMAL
        
        for widget in self.mysql_custom_frame.winfo_children():
            for child in widget.winfo_children():
                if isinstance(child, (ttk.Entry,)):
                    child.config(state=state)
    
    def _test_qdrant_connection(self, tab_type: str):
        """Test Qdrant connection."""
        def test_in_thread():
            try:
                url = getattr(self, f"{tab_type}_url_var").get()
                port = int(getattr(self, f"{tab_type}_port_var").get())
                api_key = getattr(self, f"{tab_type}_api_key_var").get()
                https = getattr(self, f"{tab_type}_https_var").get()
                
                scheme = "https" if https else "http"
                client_url = f"{scheme}://{url}:{port}"
                client = QdrantClient(url=client_url, api_key=api_key if api_key else None)
                client.get_collections()
                self.window.after(0, lambda: messagebox.showinfo(
                    "Connection Test", 
                    f"Successfully connected to {tab_type} Qdrant instance!",
                    parent=self.window
                ))
            except Exception as e:
                error_msg = str(e)
                self.window.after(0, lambda: messagebox.showerror(
                    "Connection Test Failed", 
                    f"Failed to connect to {tab_type} Qdrant:\n\n{error_msg}",
                    parent=self.window
                ))
        
        thread = threading.Thread(target=test_in_thread, daemon=True)
        thread.start()
    
    def _test_mysql_connection(self):
        """Test MySQL connection."""
        def test_in_thread():
            try:
                if self.mysql_use_ours_var.get():
                    host = get_mysql_host()
                    port = get_mysql_port()
                    user = get_mysql_user()
                    password = get_mysql_password()
                    database = get_mysql_database()
                else:
                    host = self.mysql_host_var.get()
                    port = int(self.mysql_port_var.get())
                    user = self.mysql_user_var.get()
                    password = self.mysql_password_var.get()
                    database = self.mysql_database_var.get()
                
                conn = mysql.connector.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=database
                )
                cursor = conn.cursor()
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()
                cursor.close()
                conn.close()
                self.window.after(0, lambda: messagebox.showinfo(
                    "Connection Test", 
                    f"Successfully connected to MySQL!\n\nVersion: {version[0]}",
                    parent=self.window
                ))
            except ImportError:
                self.window.after(0, lambda: messagebox.showerror(
                    "Connection Test Failed", 
                    "mysql-connector-python is not installed.\n\n"
                    "Please install it using: pip install mysql-connector-python",
                    parent=self.window
                ))
            except Exception as e:
                error_msg = str(e)
                self.window.after(0, lambda: messagebox.showerror(
                    "Connection Test Failed", 
                    f"Failed to connect to MySQL:\n\n{error_msg}",
                    parent=self.window
                ))
        
        thread = threading.Thread(target=test_in_thread, daemon=True)
        thread.start()
    
    def _on_migration_start(self):
        """Handle migration start event - disable execute button."""
        if not self._is_closing and self.window.winfo_exists():
            try:
                self.execute_button.config(state=tk.DISABLED)
            except tk.TclError:
                pass
    
    def _on_migration_complete(self):
        """Handle migration complete event - re-enable execute button."""
        if not self._is_closing and self.window.winfo_exists():
            try:
                self.execute_button.config(state=tk.NORMAL)
            except tk.TclError:
                pass
    
    def _on_close(self):
        """Handle window close event."""
        self._is_closing = True
        
        # Cancel migration if running
        if self.migration_controller.is_running():
            if messagebox.askyesno(
                "Cancel Migration?", 
                "A migration is currently running. Do you want to cancel it?\n\n"
                "Note: The current operation may complete before cancellation takes effect.",
                parent=self.window
            ):
                self.migration_controller.cancel()
                # Controller's cancel() method already emits the log message
            else:
                # User chose not to cancel, so don't destroy window yet
                self._is_closing = False
                return
        
        self.window.destroy()
    
    def _load_config_from_env_text(self):
        """Parse environment variables from text area and populate all fields."""
        env_text = self.env_text.get("1.0", tk.END).strip()
        
        if not env_text:
            messagebox.showwarning("No Input", "Please paste environment variables in the text area.", parent=self.window)
            return
        
        # Parse environment variables
        env_vars = {}
        for line in env_text.split('\n'):
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE format
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                env_vars[key] = value
        
        if not env_vars:
            messagebox.showwarning("No Variables", "No valid environment variables found in the text.", parent=self.window)
            return
        
        # Populate source Qdrant config
        if 'QDRANT_URL' in env_vars:
            url = env_vars['QDRANT_URL']
            # Strip protocol if present
            if url.startswith('http://'):
                url = url[7:]
                self.source_https_var.set(False)
            elif url.startswith('https://'):
                url = url[8:]
                self.source_https_var.set(True)
            else:
                # Try to determine from default port or assume HTTPS if port is 443
                port = env_vars.get('QDRANT_PORT', '')
                self.source_https_var.set(port == '443')
            self.source_url_var.set(url)
        if 'QDRANT_PORT' in env_vars:
            self.source_port_var.set(env_vars['QDRANT_PORT'])
        if 'QDRANT_API_KEY' in env_vars:
            self.source_api_key_var.set(env_vars['QDRANT_API_KEY'])
        
        # Populate target Qdrant config
        if 'QDRANT_URL_2' in env_vars:
            url = env_vars['QDRANT_URL_2']
            # Strip protocol if present
            if url.startswith('http://'):
                url = url[7:]
                self.target_https_var.set(False)
            elif url.startswith('https://'):
                url = url[8:]
                self.target_https_var.set(True)
            else:
                # Try to determine from default port or assume HTTPS if port is 443
                port = env_vars.get('QDRANT_PORT_2', '')
                self.target_https_var.set(port == '443')
            self.target_url_var.set(url)
        if 'QDRANT_PORT_2' in env_vars:
            self.target_port_var.set(env_vars['QDRANT_PORT_2'])
        if 'QDRANT_API_KEY_2' in env_vars:
            self.target_api_key_var.set(env_vars['QDRANT_API_KEY_2'])
        
        # Populate MySQL config
        if 'MYSQL_HOST' in env_vars:
            self.mysql_host_var.set(env_vars['MYSQL_HOST'])
        if 'MYSQL_PORT' in env_vars:
            self.mysql_port_var.set(env_vars['MYSQL_PORT'])
        if 'MYSQL_USER' in env_vars:
            self.mysql_user_var.set(env_vars['MYSQL_USER'])
        if 'MYSQL_PASSWORD' in env_vars:
            self.mysql_password_var.set(env_vars['MYSQL_PASSWORD'])
        if 'MYSQL_DATABASE' in env_vars:
            self.mysql_database_var.set(env_vars['MYSQL_DATABASE'])
        
        # If MySQL config is provided, uncheck "use ours" and enable custom fields
        if any(key in env_vars for key in ['MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE']):
            self.mysql_use_ours_var.set(False)
            self._toggle_mysql_custom()
        
        messagebox.showinfo("Config Loaded", 
                          f"Configuration loaded from {len(env_vars)} environment variables.\n\n"
                          f"Source Qdrant: {env_vars.get('QDRANT_URL', 'Not set')}\n"
                          f"Target Qdrant: {env_vars.get('QDRANT_URL_2', 'Not set')}\n"
                          f"MySQL: {env_vars.get('MYSQL_HOST', 'Not set')}",
                          parent=self.window)
    
    def _execute_migration(self):
        """Execute migration with current configuration."""
        # Create results dialog if it doesn't exist or was closed
        if self.results_dialog is None or not self.results_dialog.window.winfo_exists():
            self.results_dialog = MigrationResultsDialog(self.window, self.migration_controller)
            # Connect migration start/complete to enable/disable button
            self.migration_controller.register_callback("migration_start", self._on_migration_start)
            self.migration_controller.register_callback("migration_complete", self._on_migration_complete)
        
        # Validate inputs
        try:
            source_url = self.source_url_var.get()
            source_port = int(self.source_port_var.get())
            source_api_key = self.source_api_key_var.get()
            source_https = self.source_https_var.get()
            
            target_url = self.target_url_var.get()
            target_port = int(self.target_port_var.get())
            target_api_key = self.target_api_key_var.get()
            target_https = self.target_https_var.get()
        except ValueError as e:
            messagebox.showerror("Validation Error", f"Invalid configuration: {e}", parent=self.window)
            return
        
        # Build configs
        source_config = {
            'url': source_url,
            'port': source_port,
            'api_key': source_api_key if source_api_key else None,
            'https': source_https
        }
        
        target_config = {
            'url': target_url,
            'port': target_port,
            'api_key': target_api_key if target_api_key else None,
            'https': target_https
        }
        
        # MySQL config
        mysql_config = None
        if not self.mysql_use_ours_var.get():
            try:
                mysql_port = int(self.mysql_port_var.get())
            except ValueError:
                messagebox.showerror("Validation Error", "MySQL port must be an integer", parent=self.window)
                return
            
            mysql_config = {
                'host': self.mysql_host_var.get(),
                'port': mysql_port,
                'user': self.mysql_user_var.get(),
                'password': self.mysql_password_var.get(),
                'database': self.mysql_database_var.get()
            }
        
        # Get mode and options
        mode = self.mode_var.get()
        reverse = self.reverse_var.get()
        https = self.https_var.get()
        
        # Execute migration
        self.migration_controller.execute_migration(
            source_config=source_config,
            target_config=target_config,
            mysql_config=mysql_config,
            mode=mode,
            reverse=reverse,
            https=https
        )

