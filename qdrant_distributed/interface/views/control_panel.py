"""
Control Panel View - Left panel with operation controls.
"""

import tkinter as tk
from tkinter import ttk
from qdrant_distributed.interface.services.app_state import AppState
from qdrant_distributed.interface.controllers.operation_controller import OperationController
from qdrant_distributed.models import ShardTransferMethod


class ControlPanel(ttk.Frame):
    """Control panel for operation configuration."""
    
    def __init__(self, parent, app_state: AppState, operation_controller: OperationController):
        super().__init__(parent, padding="10")
        self.pack(fill=tk.BOTH, expand=True)
        
        self.app_state = app_state
        self.operation_controller = operation_controller
        
        self._setup_ui()
        self._bind_events()
    
    def _setup_ui(self):
        """Setup the control panel UI."""
        # Configuration Section
        config_frame = ttk.LabelFrame(self, text="Configuration", padding="12")
        config_frame.pack(fill=tk.X, pady=(0, 12))
        
        # Collection row
        collection_row = ttk.Frame(config_frame)
        collection_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(collection_row, text="Collection:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(collection_row, textvariable=self.app_state.collection_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Timeout row
        timeout_row = ttk.Frame(config_frame)
        timeout_row.pack(fill=tk.X)
        ttk.Label(timeout_row, text="Timeout (s):", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(timeout_row, textvariable=self.app_state.timeout_var, width=15).pack(side=tk.LEFT)
        
        # Operations Section
        ops_frame = ttk.LabelFrame(self, text="Operation Type", padding="12")
        ops_frame.pack(fill=tk.X, pady=(0, 12))
        
        operations = [
            ("List Shards", "list"),
            ("Move Shards", "move"),
            ("Replicate Shards", "replicate"),
            ("Abort Transfer", "abort")
        ]
        
        for idx, (text, val) in enumerate(operations):
            row = idx // 2
            col = idx % 2
            ttk.Radiobutton(ops_frame, text=text, 
                           variable=self.app_state.operation_var, value=val,
                           command=self._on_operation_change).grid(
                row=row, column=col, sticky=tk.W, padx=(0, 15), pady=5)
        
        # Parameters Section (Dynamic)
        self.params_frame = ttk.LabelFrame(self, text="Operation Parameters", padding="12")
        self.params_frame.pack(fill=tk.X, pady=(0, 12))
        
        self._create_parameter_widgets()
        
        # Options Section
        options_frame = ttk.LabelFrame(self, text="Options", padding="12")
        options_frame.pack(fill=tk.X, pady=(0, 12))
        
        self.save_checkbox = ttk.Checkbutton(options_frame, text="Save to MySQL (--save)", 
                       variable=self.app_state.save_var)
        self.save_checkbox.pack(anchor=tk.W, pady=3)
        
        self.latest_checkbox = ttk.Checkbutton(options_frame, text="Use latest from MySQL (--latest)", 
                       variable=self.app_state.latest_var)
        self.latest_checkbox.pack(anchor=tk.W, pady=3)
        
        self.last_mongo_checkbox = ttk.Checkbutton(options_frame, text="Load from MySQL (-ml)", 
                       variable=self.app_state.last_mongo_var)
        self.last_mongo_checkbox.pack(anchor=tk.W, pady=3)
        
        # Execute Button
        self.execute_button = ttk.Button(self, text="▶ Execute Operation", 
                                        command=self.operation_controller.execute_operation, width=25)
        self.execute_button.pack(pady=(10, 0))
        
        # Initialize UI state
        self._on_operation_change()
    
    def _create_parameter_widgets(self):
        """Create parameter widgets."""
        # From/To Peer Frame
        self.peer_frame = ttk.Frame(self.params_frame)
        
        from_peer_row = ttk.Frame(self.peer_frame)
        from_peer_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(from_peer_row, text="From Peer ID:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(from_peer_row, textvariable=self.app_state.from_peer_var, width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        to_peer_row = ttk.Frame(self.peer_frame)
        to_peer_row.pack(fill=tk.X)
        ttk.Label(to_peer_row, text="To Peer ID:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(to_peer_row, textvariable=self.app_state.to_peer_var, width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Shard ID Frame
        self.shard_frame = ttk.Frame(self.params_frame)
        shard_row = ttk.Frame(self.shard_frame)
        shard_row.pack(fill=tk.X)
        ttk.Label(shard_row, text="Shard ID:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(shard_row, textvariable=self.app_state.shard_id_var, width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Method Frame
        self.method_frame = ttk.Frame(self.params_frame)
        method_row = ttk.Frame(self.method_frame)
        method_row.pack(fill=tk.X)
        ttk.Label(method_row, text="Transfer Method:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Combobox(method_row, textvariable=self.app_state.method_var, 
                    values=ShardTransferMethod.list_methods(), 
                    state="readonly", width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    def _on_operation_change(self):
        """Update UI based on selected operation."""
        operation = self.app_state.operation_var.get()
        
        # Hide all parameter frames
        self.peer_frame.pack_forget()
        self.shard_frame.pack_forget()
        self.method_frame.pack_forget()
        
        # Enable/disable and clear options based on operation type
        # --save: Available for all operations
        self.save_checkbox.config(state="normal")
        
        # --latest: Only for move and replicate
        if operation in ["move", "replicate"]:
            self.latest_checkbox.config(state="normal")
        else:
            self.latest_checkbox.config(state="disabled")
            self.app_state.latest_var.set(False)
        
        # -ml (Load from MySQL): Only for list
        if operation == "list":
            self.last_mongo_checkbox.config(state="normal")
        else:
            self.last_mongo_checkbox.config(state="disabled")
            self.app_state.last_mongo_var.set(False)
        
        # Show relevant parameter frames based on operation
        if operation in ["move", "replicate"]:
            self.peer_frame.pack(fill=tk.X, pady=(0, 8))
            self.method_frame.pack(fill=tk.X)
        elif operation == "abort":
            self.peer_frame.pack(fill=tk.X, pady=(0, 8))
            self.shard_frame.pack(fill=tk.X)
        # list operation doesn't need parameter frames
    
    def _bind_events(self):
        """Bind UI events."""
        self.app_state.operation_var.trace_add("write", lambda *args: self._on_operation_change())
    
    def set_execute_button_state(self, state: str):
        """Set execute button state."""
        self.execute_button.config(state=state)

