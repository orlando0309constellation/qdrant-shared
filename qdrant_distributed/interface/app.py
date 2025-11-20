"""
Qdrant Manager Desktop Application using Tkinter
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import sys
from io import StringIO
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from qdrant_distributed.constant import SHARED_COLLECTION_NAME
from qdrant_distributed.client.qdrant_client import QdrantClientManager
from qdrant_distributed import ShardOperations, ClusterOperations
from qdrant_distributed.models import ShardTransferMethod, PeerInfo
from qdrant_distributed.exceptions import QdrantShardingError, ValidationError
from qdrant_distributed.config import MongoManager
from qdrant_distributed.services.mongo_service import MongoService
from qdrant_distributed.models.shard import ShardInfo
from typing import Dict, List


class QdrantManagerApp:
    """Desktop GUI application for Qdrant cluster management."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Qdrant Cluster Manager")
        self.root.geometry("1200x850")
        
        # Set theme
        style = ttk.Style()
        style.theme_use('clam')
        
        # Variables
        self.operation_var = tk.StringVar(value="list")
        self.collection_var = tk.StringVar(value=SHARED_COLLECTION_NAME)
        self.from_peer_var = tk.StringVar()
        self.to_peer_var = tk.StringVar()
        self.shard_id_var = tk.StringVar()
        self.method_var = tk.StringVar(value="stream_records")
        self.timeout_var = tk.StringVar(value="120")
        self.save_var = tk.BooleanVar(value=False)
        self.latest_var = tk.BooleanVar(value=False)
        self.last_mongo_var = tk.BooleanVar(value=False)
        
        # Services
        self.shard_ops: Optional[ShardOperations] = None
        self.cluster_ops: Optional[ClusterOperations] = None
        self.mongo_service: Optional[MongoService] = None
        self.is_initialized = False
        
        # Setup UI
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface with improved layout."""
        # Main container - use pack for better control
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
        
        # ========== LEFT PANEL - CONTROLS ==========
        
        # 1. Configuration Section
        config_frame = ttk.LabelFrame(left_panel, text="Configuration", padding="12")
        config_frame.pack(fill=tk.X, pady=(0, 12))
        
        # Collection row
        collection_row = ttk.Frame(config_frame)
        collection_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(collection_row, text="Collection:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(collection_row, textvariable=self.collection_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Timeout row
        timeout_row = ttk.Frame(config_frame)
        timeout_row.pack(fill=tk.X)
        ttk.Label(timeout_row, text="Timeout (s):", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(timeout_row, textvariable=self.timeout_var, width=15).pack(side=tk.LEFT)
        
        # 2. Operations Section
        ops_frame = ttk.LabelFrame(left_panel, text="Operation Type", padding="12")
        ops_frame.pack(fill=tk.X, pady=(0, 12))
        
        # Operation buttons in a grid
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
                           variable=self.operation_var, value=val,
                           command=self.on_operation_change).grid(
                row=row, column=col, sticky=tk.W, padx=(0, 15), pady=5)
        
        # 3. Parameters Section (Dynamic)
        self.params_frame = ttk.LabelFrame(left_panel, text="Operation Parameters", padding="12")
        self.params_frame.pack(fill=tk.X, pady=(0, 12))
        
        # Create parameter widgets
        self.create_parameter_widgets()
        
        # 4. Options Section
        options_frame = ttk.LabelFrame(left_panel, text="Options", padding="12")
        options_frame.pack(fill=tk.X, pady=(0, 12))
        
        self.save_check = ttk.Checkbutton(options_frame, text="Save to MongoDB (--save)", 
                                         variable=self.save_var)
        self.save_check.pack(anchor=tk.W, pady=3)
                       
        self.latest_check = ttk.Checkbutton(options_frame, text="Use latest from MongoDB (--latest)", 
                                           variable=self.latest_var)
        self.latest_check.pack(anchor=tk.W, pady=3)
        
        self.last_mongo_check = ttk.Checkbutton(options_frame, text="Load from MongoDB (-ml)", 
                                               variable=self.last_mongo_var)
        self.last_mongo_check.pack(anchor=tk.W, pady=3)
        
        # 5. Execute Button
        self.execute_button = ttk.Button(left_panel, text="▶ Execute Operation", 
                                        command=self.execute_operation, width=25)
        self.execute_button.pack(pady=(10, 0))
        
        # ========== RIGHT PANEL - OUTPUT ==========
        
        output_frame = ttk.LabelFrame(right_panel, text="Output & Logs", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        # Output text area
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, 
                                                      font=("Consolas", 10), 
                                                      bg="#1e1e1e", fg="#d4d4d4",
                                                      insertbackground="#ffffff")
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure text tags for better formatting
        self.output_text.tag_config("header", foreground="#4ec9b0", font=("Consolas", 10, "bold"))
        self.output_text.tag_config("success", foreground="#4ec9b0")
        self.output_text.tag_config("error", foreground="#f48771")
        self.output_text.tag_config("warning", foreground="#dcdcaa")
        self.output_text.tag_config("info", foreground="#569cd6")
        
        # Status Bar (at bottom of root)
        self.status_label = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W, padding=5)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Initialize state
        self.on_operation_change()

    def create_parameter_widgets(self):
        """Create all parameter widgets."""
        # From/To Peer Frame
        self.peer_frame = ttk.Frame(self.params_frame)
        
        from_peer_row = ttk.Frame(self.peer_frame)
        from_peer_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(from_peer_row, text="From Peer ID:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(from_peer_row, textvariable=self.from_peer_var, width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        to_peer_row = ttk.Frame(self.peer_frame)
        to_peer_row.pack(fill=tk.X)
        ttk.Label(to_peer_row, text="To Peer ID:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(to_peer_row, textvariable=self.to_peer_var, width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Shard ID Frame
        self.shard_frame = ttk.Frame(self.params_frame)
        shard_row = ttk.Frame(self.shard_frame)
        shard_row.pack(fill=tk.X)
        ttk.Label(shard_row, text="Shard ID:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(shard_row, textvariable=self.shard_id_var, width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Method Frame
        self.method_frame = ttk.Frame(self.params_frame)
        method_row = ttk.Frame(self.method_frame)
        method_row.pack(fill=tk.X)
        ttk.Label(method_row, text="Transfer Method:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Combobox(method_row, textvariable=self.method_var, 
                    values=ShardTransferMethod.list_methods(), 
                    state="readonly", width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def on_operation_change(self):
        """Update UI based on selected operation."""
        operation = self.operation_var.get()
        
        # Clear dynamic parameters
        for widget in self.params_frame.winfo_children():
            widget.pack_forget()
            
        # Reset option states
        self.latest_check.config(state=tk.NORMAL)
        self.last_mongo_check.config(state=tk.NORMAL)
        
        if operation == "list":
            # No extra parameters needed
            self.latest_check.config(state=tk.DISABLED)
            
        elif operation in ["move", "replicate"]:
            self.peer_frame.pack(fill=tk.X, pady=5)
            self.method_frame.pack(fill=tk.X, pady=5)
            self.last_mongo_check.config(state=tk.DISABLED)
            
        elif operation == "abort":
            self.peer_frame.pack(fill=tk.X, pady=5)
            self.shard_frame.pack(fill=tk.X, pady=5)
            self.latest_check.config(state=tk.DISABLED)
            self.last_mongo_check.config(state=tk.DISABLED)

    def log_output(self, text: str, tag: str = None):
        """Add text to output area with optional formatting."""
        self.output_text.insert(tk.END, text + "\n", tag)
        self.output_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_output(self):
        """Clear output area."""
        self.output_text.delete(1.0, tk.END)
    
    def set_status(self, text: str):
        """Update status bar."""
        self.status_label.config(text=text)
        self.root.update_idletasks()
    
    def validate_inputs(self) -> bool:
        """Validate user inputs."""
        operation = self.operation_var.get()
        
        if operation in ["move", "replicate"]:
            if not self.from_peer_var.get() or not self.to_peer_var.get():
                messagebox.showerror("Validation Error", 
                                   "From Peer and To Peer are required for move/replicate operations")
                return False
            try:
                int(self.from_peer_var.get())
                int(self.to_peer_var.get())
            except ValueError:
                messagebox.showerror("Validation Error", "Peer IDs must be integers")
                return False
                
        elif operation == "abort":
            if not self.from_peer_var.get() or not self.to_peer_var.get() or not self.shard_id_var.get():
                messagebox.showerror("Validation Error", 
                                   "From Peer, To Peer, and Shard ID are required for abort operation")
                return False
            try:
                int(self.from_peer_var.get())
                int(self.to_peer_var.get())
                int(self.shard_id_var.get())
            except ValueError:
                messagebox.showerror("Validation Error", "Peer IDs and Shard ID must be integers")
                return False
        
        if self.last_mongo_var.get() and operation != "list":
            messagebox.showerror("Validation Error", 
                               "-ml (Load from MongoDB) can only be used with List operation")
            return False
        
        if self.latest_var.get() and operation not in ["move", "replicate"]:
            messagebox.showerror("Validation Error", 
                               "--latest can only be used with Move or Replicate operations")
            return False
        
        try:
            int(self.timeout_var.get())
        except ValueError:
            messagebox.showerror("Validation Error", "Timeout must be an integer")
            return False
        
        return True
    
    def ensure_mongo_initialized(self):
        """Ensure MongoDB is initialized if needed."""
        if self.mongo_service is None:
            if self.save_var.get() or self.last_mongo_var.get() or self.latest_var.get():
                self.log_output("🔌 Initializing MongoDB connection...", "info")
                MongoManager.initialize()
                self.mongo_service = MongoService()
                self.log_output("✅ MongoDB connection initialized", "success")
    
    def initialize_services(self):
        """Initialize Qdrant and MongoDB services."""
        if not self.is_initialized:
            self.log_output("🔌 Initializing Qdrant client...", "info")
            QdrantClientManager.initialize()
            self.log_output("✅ Qdrant client initialized", "success")
            
            # Initialize operations
            self.shard_ops = ShardOperations()
            self.cluster_ops = ClusterOperations()
            
            self.is_initialized = True
        
        # Always check if MongoDB is needed (in case flags changed)
        self.ensure_mongo_initialized()
    
    def convert_peer_shards_to_peer_info(self, peer_shards: Dict[int, List[ShardInfo]], 
                                        peers_dict: Dict[str, any]) -> List[PeerInfo]:
        """Convert peer_shards dictionary to list of PeerInfo objects."""
        peer_info_list = []
        for peer_id, shards in peer_shards.items():
            peer_data = peers_dict.get(str(peer_id), {})
            uri = peer_data.get("uri", "")
            peer_info = PeerInfo(peer_id=peer_id, uri=uri, local_shards=shards)
            peer_info_list.append(peer_info)
        return peer_info_list
    
    def execute_operation_thread(self):
        """Execute the selected operation in a separate thread."""
        try:
            # Redirect stdout to capture print statements
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            
            operation = self.operation_var.get()
            collection = self.collection_var.get()
            timeout = int(self.timeout_var.get())
            
            self.initialize_services()
            
            if operation == "list":
                self.execute_list_operation(collection, timeout)
            elif operation == "move":
                self.execute_move_operation(collection, timeout)
            elif operation == "replicate":
                self.execute_replicate_operation(collection, timeout)
            elif operation == "abort":
                self.execute_abort_operation(collection, timeout)
            
            # Get captured output
            output = sys.stdout.getvalue()
            if output:
                self.log_output(output)
            
            sys.stdout = old_stdout
            
            self.log_output("\n" + "=" * 80, "header")
            self.log_output("✨ Operation completed successfully", "success")
            self.log_output("=" * 80, "header")
            self.set_status("Operation completed successfully")
            
        except Exception as e:
            sys.stdout = old_stdout
            self.log_output(f"\n❌ Error: {type(e).__name__}: {str(e)}", "error")
            self.set_status(f"Error: {str(e)}")
            messagebox.showerror("Operation Failed", str(e))
        finally:
            self.execute_button.config(state=tk.NORMAL)
    
    def execute_list_operation(self, collection: str, timeout: int):
        """Execute list shards operation."""
        self.log_output("📋 Listing all local shards from each peer in the cluster\n", "info")
        
        if self.last_mongo_var.get():
            self.ensure_mongo_initialized()
            if self.mongo_service is None:
                raise ValueError("MongoDB service not initialized. Please check MongoDB connection settings.")
            # Fetch once and reuse to avoid duplicate queries
            latest_doc = self.mongo_service.get_latest_peers()
            peer_shards = self.mongo_service.get_latest_peers_as_dict(latest_doc)
            peer_uris = self.mongo_service.get_latest_peer_uris(latest_doc)
            self.display_shard_list(peer_shards, peer_uris)
        else:
            peer_shards = self.cluster_ops.list_all_shards(collection_name=collection, timeout=timeout)
            
            # Get peer URIs
            from qdrant_distributed.client import ClusterClient
            cluster_client = ClusterClient()
            peers_dict, _ = cluster_client.get_peers(timeout)
            peer_uris = {int(pid): peer_data.get("uri", "") for pid, peer_data in peers_dict.items()}
            
            self.display_shard_list(peer_shards, peer_uris)
            
            # Save to MongoDB if requested
            if self.save_var.get():
                self.ensure_mongo_initialized()
                if self.mongo_service is None:
                    raise ValueError("MongoDB service not initialized. Please check MongoDB connection settings.")
                self.log_output("\n💾 Saving peer information to MongoDB...", "info")
                peer_info_list = self.convert_peer_shards_to_peer_info(peer_shards, peers_dict)
                self.mongo_service.save_peers(peer_info_list)
                self.log_output("✓ Peer information saved to MongoDB", "success")
    
    def execute_move_operation(self, collection: str, timeout: int):
        """Execute move shards operation."""
        from_peer = int(self.from_peer_var.get())
        to_peer = int(self.to_peer_var.get())
        method = self.method_var.get()
        
        self.log_output(f"🚀 Moving all shards from peer {from_peer} to peer {to_peer}", "info")
        self.log_output(f"   Method: {method}\n", "info")
        
        # Get shard information
        if self.latest_var.get():
            self.ensure_mongo_initialized()
            if self.mongo_service is None:
                raise ValueError("MongoDB service not initialized. Please check MongoDB connection settings.")
            self.log_output("📋 Getting shard information from MongoDB (latest)...", "info")
            all_peer_shards = self.mongo_service.get_latest_peers_as_dict()
            self.log_output("✓ Retrieved peer information from MongoDB\n", "success")
        else:
            self.log_output("📋 Getting shard information from peers...", "info")
            all_peer_shards = self.cluster_ops.list_all_shards(collection_name=collection, timeout=timeout)
            self.log_output("")
        
        # Execute move
        self.shard_ops.move_all(
            collection_name=collection,
            all_shards=all_peer_shards,
            from_peer_id=from_peer,
            to_peer_id=to_peer,
            method=ShardTransferMethod(method),
            timeout=timeout
        )
    
    def execute_replicate_operation(self, collection: str, timeout: int):
        """Execute replicate shards operation."""
        from_peer = int(self.from_peer_var.get())
        to_peer = int(self.to_peer_var.get())
        method = self.method_var.get()
        
        self.log_output(f"🔁 Replicating all shards from peer {from_peer} to peer {to_peer}", "info")
        self.log_output(f"   Method: {method}\n", "info")
        
        # Get shard information
        if self.latest_var.get():
            self.ensure_mongo_initialized()
            if self.mongo_service is None:
                raise ValueError("MongoDB service not initialized. Please check MongoDB connection settings.")
            self.log_output("📋 Getting shard information from MongoDB (latest)...", "info")
            all_peer_shards = self.mongo_service.get_latest_peers_as_dict()
            self.log_output("✓ Retrieved peer information from MongoDB\n", "success")
        else:
            self.log_output("📋 Getting shard information from peers...", "info")
            all_peer_shards = self.cluster_ops.list_all_shards(collection_name=collection, timeout=timeout)
            self.log_output("")
        
        # Execute replicate
        self.shard_ops.replicate_all(
            collection_name=collection,
            all_shards=all_peer_shards,
            from_peer_id=from_peer,
            to_peer_id=to_peer,
            method=ShardTransferMethod(method),
            timeout=timeout
        )
    
    def execute_abort_operation(self, collection: str, timeout: int):
        """Execute abort transfer operation."""
        from_peer = int(self.from_peer_var.get())
        to_peer = int(self.to_peer_var.get())
        shard_id = int(self.shard_id_var.get())
        
        self.log_output(f"🛑 Aborting transfer for shard {shard_id} from peer {from_peer} to peer {to_peer}\n", "warning")
        
        result = self.shard_ops.abort_transfer(
            collection_name=collection,
            shard_id=shard_id,
            from_peer_id=from_peer,
            to_peer_id=to_peer,
            timeout=timeout
        )
        
        self.log_output(f"Status: {result.get('status')}", "info")
        self.log_output(f"Result: {result.get('result')}", "info")
        self.log_output(f"Time: {result.get('time', 0):.3f}s", "info")
    
    def display_shard_list(self, peer_shards: Dict[int, List[ShardInfo]], peer_uris: Dict[int, str]):
        """Display shard list in output area."""
        self.log_output("=" * 80, "header")
        self.log_output("✅ Successfully retrieved shard information from all peers!", "success")
        self.log_output("=" * 80, "header")
        self.log_output("")
        
        if not peer_shards:
            self.log_output("⚠️  No peers found or no shard information available", "warning")
            return
        
        total_shards = 0
        total_points = 0
        
        for peer_id, shards in sorted(peer_shards.items()):
            uri = peer_uris.get(peer_id, "") if peer_uris else ""
            if uri:
                self.log_output(f"📍 Peer {peer_id}({uri}):", "info")
            else:
                self.log_output(f"📍 Peer {peer_id}:", "info")
            self.log_output(f"   {'='*70}")
            
            if not shards:
                self.log_output("   No local shards", "warning")
            else:
                for shard in shards:
                    shard_id = shard.shard_id
                    points_count = shard.points_count
                    state = shard.state.value
                    total_shards += 1
                    total_points += points_count
                    
                    self.log_output(f"   ├─ Shard {shard_id}")
                    self.log_output(f"   │  ├─ Points: {points_count:,}")
                    self.log_output(f"   │  └─ State: {state}")
            
            self.log_output("")
        
        self.log_output("=" * 80, "header")
        self.log_output(f"📊 Summary:", "header")
        self.log_output(f"   Total Peers: {len(peer_shards)}")
        self.log_output(f"   Total Local Shards: {total_shards}")
        self.log_output(f"   Total Points: {total_points:,}")
        self.log_output("=" * 80, "header")
    
    def execute_operation(self):
        """Execute button click handler."""
        if not self.validate_inputs():
            return
        
        self.clear_output()
        self.set_status("Running operation...")
        self.execute_button.config(state=tk.DISABLED)
        
        # Run operation in separate thread to avoid blocking UI
        thread = threading.Thread(target=self.execute_operation_thread, daemon=True)
        thread.start()


def main():
    """Main entry point for the desktop application."""
    root = tk.Tk()
    app = QdrantManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
