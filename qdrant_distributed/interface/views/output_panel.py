"""
Output Panel View - Right panel with results and logs.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List
from qdrant_distributed.models.shard import ShardInfo
from qdrant_distributed.interface.services.app_state import AppState
from qdrant_distributed.interface.widgets.progress_bar import ProgressBar
from qdrant_distributed.interface.widgets.log_viewer import LogViewer
from qdrant_distributed.interface.widgets.shard_tree import ShardTree


class OutputPanel(ttk.Frame):
    """Output panel for displaying results and logs."""
    
    def __init__(self, parent, app_state: AppState, status_callback=None):
        super().__init__(parent, padding="10")
        self.pack(fill=tk.BOTH, expand=True)
        
        self.app_state = app_state
        self.status_callback = status_callback
        
        # Create output frame
        output_frame = ttk.LabelFrame(self, text="Output & Results", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(output_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Progress bar (packed before notebook when shown)
        self.progress_bar = ProgressBar(output_frame, before_widget=self.notebook)
        
        # Tab 1: Results
        results_frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(results_frame, text="📊 Results")
        
        # Summary panel
        summary_frame = ttk.LabelFrame(results_frame, text="Summary", padding="10")
        summary_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.summary_label = ttk.Label(summary_frame, text="No data available", 
                                       font=("Segoe UI", 10))
        self.summary_label.pack(anchor=tk.W)
        
        # Export buttons
        export_frame = ttk.Frame(summary_frame)
        export_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(export_frame, text="📋 Copy to Clipboard", 
                  command=self._copy_to_clipboard, width=20).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(export_frame, text="💾 Export CSV", 
                  command=self._export_csv, width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(export_frame, text="💾 Export JSON", 
                  command=self._export_json, width=15).pack(side=tk.LEFT)
        
        # Treeview for shard display
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        
        # Create treeview
        self.shard_tree = ShardTree(tree_frame,
                                    yscrollcommand=tree_scroll_y.set,
                                    xscrollcommand=tree_scroll_x.set)
        
        # Configure scrollbars
        tree_scroll_y.config(command=self.shard_tree.yview)
        tree_scroll_x.config(command=self.shard_tree.xview)
        
        # Setup column sorting
        for col in ("Peer ID", "Peer URI", "Shard ID", "Points", "State"):
            self.shard_tree.heading(col, command=lambda c=col: self.shard_tree.sort_by_column(c))
        
        # Bind double-click to copy Peer ID
        self.shard_tree.bind("<Double-1>", self._on_tree_double_click)
        
        # Grid layout
        self.shard_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Tab 2: Logs
        logs_frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(logs_frame, text="📝 Logs")
        
        self.log_viewer = LogViewer(logs_frame)
        self.log_viewer.pack(fill=tk.BOTH, expand=True)
    
    def display_shards(self, peer_shards: Dict[int, List[ShardInfo]], peer_uris: Dict[int, str]):
        """Display shards in the treeview and update summary."""
        # Switch to Results tab
        self.notebook.select(0)
        
        # Display in treeview
        self.shard_tree.display_shards(peer_shards, peer_uris)
        
        # Update summary
        if not peer_shards:
            self.summary_label.config(text="⚠️  No peers found or no shard information available")
            return
        
        total_shards = sum(len(shards) for shards in peer_shards.values())
        total_points = sum(shard.points_count for shards in peer_shards.values() for shard in shards)
        
        summary_text = (
            f"📊 Total Peers: {len(peer_shards)} | "
            f"Total Shards: {total_shards} | "
            f"Total Local points: {total_points:,}"
        )
        self.summary_label.config(text=summary_text)
    
    def _copy_to_clipboard(self):
        """Copy shard data to clipboard."""
        if not self.app_state.current_peer_shards:
            return
        
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Peer ID", "Peer URI", "Shard ID", "Points", "State"])
        
        for peer_id, shards in sorted(self.app_state.current_peer_shards.items()):
            uri = self.app_state.current_peer_uris.get(peer_id, "") if self.app_state.current_peer_uris else ""
            for shard in shards:
                writer.writerow([peer_id, uri, shard.shard_id, shard.points_count, shard.state.value])
        
        # Get root window from parent hierarchy
        root = self.winfo_toplevel()
        root.clipboard_clear()
        root.clipboard_append(output.getvalue())
        output.close()
    
    def _export_csv(self):
        """Export shard data to CSV file."""
        from tkinter import filedialog
        import csv
        
        if not self.app_state.current_peer_shards:
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Peer ID", "Peer URI", "Shard ID", "Points", "State"])
                
                for peer_id, shards in sorted(self.app_state.current_peer_shards.items()):
                    uri = self.app_state.current_peer_uris.get(peer_id, "") if self.app_state.current_peer_uris else ""
                    for shard in shards:
                        writer.writerow([peer_id, uri, shard.shard_id, shard.points_count, shard.state.value])
    
    def _export_json(self):
        """Export shard data to JSON file."""
        from tkinter import filedialog
        import json
        
        if not self.app_state.current_peer_shards:
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            data = {}
            for peer_id, shards in sorted(self.app_state.current_peer_shards.items()):
                uri = self.app_state.current_peer_uris.get(peer_id, "") if self.app_state.current_peer_uris else ""
                data[peer_id] = {
                    "uri": uri,
                    "shards": [
                        {
                            "shard_id": shard.shard_id,
                            "points_count": shard.points_count,
                            "state": shard.state.value
                        }
                        for shard in shards
                    ]
                }
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
    
    def _on_tree_double_click(self, event):
        """Handle double-click on treeview to copy Peer ID."""
        # Get the item under the cursor
        item = self.shard_tree.identify_row(event.y)
        if not item:
            return
        
        # Get the column under the cursor
        column = self.shard_tree.identify_column(event.x)
        
        # Check if it's the Peer ID column (column index 1, but treeview uses #1, #2, etc.)
        if column == "#1":  # Peer ID is the first column
            # Get the Peer ID value
            peer_id = self.shard_tree.set(item, "Peer ID")
            if peer_id:
                # Get root window from parent hierarchy
                root = self.winfo_toplevel()
                # Copy to clipboard
                root.clipboard_clear()
                root.clipboard_append(str(peer_id))
                # Update status bar at the bottom
                if self.status_callback:
                    self.status_callback(f"✓ Copied Peer ID {peer_id} to clipboard")

