"""
Shard Tree Widget - Displays shard information in a treeview.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Set
from qdrant_distributed.models.shard import ShardInfo


class ShardTree(ttk.Treeview):
    """Treeview widget for displaying shard information."""
    
    def __init__(self, parent, **kwargs):
        columns = ("Peer ID", "Peer URI", "Shard ID", "Points", "State")
        super().__init__(parent, columns=columns, show="headings", **kwargs)
        self._setup_columns()
        self._setup_tags()
        self.selection_before_click: Set[str] = set()
        self.sort_reverse: Dict[str, bool] = {col: False for col in columns}
    
    def _setup_columns(self):
        """Setup treeview columns."""
        self.heading("Peer ID", text="Peer ID")
        self.heading("Peer URI", text="Peer URI")
        self.heading("Shard ID", text="Shard ID")
        self.heading("Points", text="Points")
        self.heading("State", text="State")
        
        self.column("Peer ID", width=80, anchor=tk.CENTER)
        self.column("Peer URI", width=200, anchor=tk.W)
        self.column("Shard ID", width=80, anchor=tk.CENTER)
        self.column("Points", width=120, anchor=tk.E)
        self.column("State", width=120, anchor=tk.CENTER)
    
    def _setup_tags(self):
        """Setup color tags for shard states."""
        self.tag_configure("active", background="#d4edda")
        self.tag_configure("dead", background="#f8d7da")
        self.tag_configure("partial", background="#fff3cd")
        self.tag_configure("replica", background="#d1ecf1")
    
    def _get_state_tag(self, state: str) -> str:
        """Get color tag for shard state."""
        state_lower = state.lower()
        if "active" in state_lower:
            return "active"
        elif "dead" in state_lower:
            return "dead"
        elif "partial" in state_lower:
            return "partial"
        elif "replica" in state_lower:
            return "replica"
        return ""
    
    def display_shards(self, peer_shards: Dict[int, List[ShardInfo]], peer_uris: Dict[int, str]):
        """Display shards in the treeview."""
        # Clear existing items
        for item in self.get_children():
            self.delete(item)
        
        # Populate treeview
        for peer_id, shards in sorted(peer_shards.items()):
            uri = peer_uris.get(peer_id, "") if peer_uris else ""
            
            for shard in shards:
                tag = self._get_state_tag(shard.state.value)
                self.insert('', tk.END, values=(
                    peer_id,
                    uri,
                    shard.shard_id,
                    f"{shard.points_count:,}",
                    shard.state.value
                ), tags=(tag,))
    
    def get_selected_shard_ids(self, from_peer: int) -> List[int]:
        """Get selected shard IDs from the specified peer."""
        selected_shard_ids = []
        selected_items = self.selection()
        
        for item in selected_items:
            item_peer_id = int(self.set(item, "Peer ID"))
            if item_peer_id == from_peer:
                shard_id = int(self.set(item, "Shard ID"))
                selected_shard_ids.append(shard_id)
        
        return sorted(list(set(selected_shard_ids)))
    
    def sort_by_column(self, column: str):
        """Sort treeview by column."""
        items = [(self.set(item, column), item) for item in self.get_children('')]
        
        # Try to convert to numbers for numeric columns
        try:
            items.sort(key=lambda t: int(t[0]) if t[0].isdigit() else float('inf'), reverse=self.sort_reverse[column])
        except (ValueError, TypeError):
            items.sort(key=lambda t: str(t[0]).lower(), reverse=self.sort_reverse[column])
        
        for index, (val, item) in enumerate(items):
            self.move(item, '', index)
        
        self.sort_reverse[column] = not self.sort_reverse[column]

