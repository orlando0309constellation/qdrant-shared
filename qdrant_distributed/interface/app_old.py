"""
Qdrant Manager Desktop Application using Tkinter
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import sys
from io import StringIO
from typing import Optional, Dict, List, Tuple
import csv
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from qdrant_distributed.constant import SHARED_COLLECTION_NAME
from qdrant_distributed.client.qdrant_client import QdrantClientManager
from qdrant_distributed import ShardOperations, ClusterOperations
from qdrant_distributed.models import ShardTransferMethod, PeerInfo
from qdrant_distributed.exceptions import QdrantShardingError, ValidationError
from qdrant_distributed.config import MySQLManager
from qdrant_distributed.services.mysql_service import MySQLService
from qdrant_distributed.services.config_service import ConfigService
from qdrant_distributed.models.shard import ShardInfo


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
        
        # Configuration - load from SQLite or use default
        ConfigService.initialize()
        self.replicate_factor = ConfigService.get_int("replicate_factor", default=2)
        
        # Services
        self.shard_ops: Optional[ShardOperations] = None
        self.cluster_ops: Optional[ClusterOperations] = None
        self.mysql_service: Optional[MySQLService] = None
        self.is_initialized = False
        
        # Store current shard data for export
        self.current_peer_shards: Optional[Dict[int, List[ShardInfo]]] = None
        self.current_peer_uris: Optional[Dict[int, str]] = None
        
        # Track selection before click for toggle detection
        self.selection_before_click = set()
        
        # Setup UI
        self.setup_menu()
        self.setup_ui()
    
    def setup_menu(self):
        """Setup the menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Configuration menu
        config_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configuration", menu=config_menu)
        config_menu.add_command(label="Settings...", command=self.open_config_dialog)
        
    def open_config_dialog(self):
        """Open the configuration dialog window."""
        config_window = tk.Toplevel(self.root)
        config_window.title("Configuration Settings")
        config_window.geometry("650x700")
        config_window.resizable(False, False)
        config_window.transient(self.root)
        config_window.grab_set()
        
        # Center the window
        config_window.update_idletasks()
        x = (config_window.winfo_screenwidth() // 2) - (config_window.winfo_width() // 2)
        y = (config_window.winfo_screenheight() // 2) - (config_window.winfo_height() // 2)
        config_window.geometry(f"+{x}+{y}")
        
        # Main frame with scrollable content
        main_frame = ttk.Frame(config_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Configuration Settings", 
                               font=("Segoe UI", 14, "bold"))
        title_label.pack(pady=(0, 15))
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # ========== TAB 1: Replication Settings ==========
        replicate_tab = ttk.Frame(notebook, padding="15")
        notebook.add(replicate_tab, text="Replication")
        
        replicate_frame = ttk.LabelFrame(replicate_tab, text="Replication Settings", padding="15")
        replicate_frame.pack(fill=tk.X, pady=(0, 10))
        
        desc_label = ttk.Label(replicate_frame, 
                              text="Replicate Factor: Maximum number of copies of a shard allowed across peers.\n"
                                   "When moving or replicating shards, the system will check if this limit would be exceeded.",
                              wraplength=580, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W, pady=(0, 15))
        
        replicate_row = ttk.Frame(replicate_frame)
        replicate_row.pack(fill=tk.X)
        ttk.Label(replicate_row, text="Replicate Factor:", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        replicate_var = tk.StringVar(value=str(self.replicate_factor))
        ttk.Entry(replicate_row, textvariable=replicate_var, width=15).pack(side=tk.LEFT)
        
        # ========== TAB 2: Qdrant Settings ==========
        qdrant_tab = ttk.Frame(notebook, padding="15")
        notebook.add(qdrant_tab, text="Qdrant")
        
        qdrant_frame = ttk.LabelFrame(qdrant_tab, text="Qdrant Connection Settings", padding="15")
        qdrant_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Load current values from ConfigService or defaults
        qdrant_url_var = tk.StringVar(value=ConfigService.get("QDRANT_URL") or "localhost")
        qdrant_port_var = tk.StringVar(value=ConfigService.get("QDRANT_PORT") or "6333")
        qdrant_api_key_var = tk.StringVar(value=ConfigService.get("QDRANT_API_KEY") or "")
        https_val = ConfigService.get("QDRANT_HTTPS")
        qdrant_https_var = tk.BooleanVar(value=(https_val or "true").lower() == "true")
        
        # URL
        url_row = ttk.Frame(qdrant_frame)
        url_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(url_row, text="URL:", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(url_row, textvariable=qdrant_url_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Port
        port_row = ttk.Frame(qdrant_frame)
        port_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(port_row, text="Port:", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(port_row, textvariable=qdrant_port_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # API Key
        api_key_row = ttk.Frame(qdrant_frame)
        api_key_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(api_key_row, text="API Key:", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(api_key_row, textvariable=qdrant_api_key_var, width=40, show="*").pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # HTTPS
        https_row = ttk.Frame(qdrant_frame)
        https_row.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(https_row, text="Use HTTPS:", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(https_row, variable=qdrant_https_var).pack(side=tk.LEFT)
        
        # Test Connection Button
        qdrant_test_frame = ttk.Frame(qdrant_frame)
        qdrant_test_frame.pack(fill=tk.X)
        qdrant_test_button = ttk.Button(qdrant_test_frame, text="Test Connection", 
                                        command=lambda: self.test_qdrant_connection(
                                            qdrant_url_var.get(),
                                            qdrant_port_var.get(),
                                            qdrant_api_key_var.get(),
                                            qdrant_https_var.get(),
                                            config_window
                                        ))
        qdrant_test_button.pack(side=tk.LEFT)
        
        # ========== TAB 3: MySQL Settings ==========
        mysql_tab = ttk.Frame(notebook, padding="15")
        notebook.add(mysql_tab, text="MySQL")
        
        mysql_frame = ttk.LabelFrame(mysql_tab, text="MySQL Connection Settings", padding="15")
        mysql_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Load current values from ConfigService or defaults
        mysql_host_var = tk.StringVar(value=ConfigService.get("MYSQL_HOST") or "localhost")
        mysql_port_var = tk.StringVar(value=ConfigService.get("MYSQL_PORT") or "3306")
        mysql_user_var = tk.StringVar(value=ConfigService.get("MYSQL_USER") or "root")
        mysql_password_var = tk.StringVar(value=ConfigService.get("MYSQL_PASSWORD") or "")
        mysql_database_var = tk.StringVar(value=ConfigService.get("MYSQL_DATABASE") or "qdrant_manager")
        
        # Host
        mysql_host_row = ttk.Frame(mysql_frame)
        mysql_host_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(mysql_host_row, text="Host:", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(mysql_host_row, textvariable=mysql_host_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Port
        mysql_port_row = ttk.Frame(mysql_frame)
        mysql_port_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(mysql_port_row, text="Port:", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(mysql_port_row, textvariable=mysql_port_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # User
        mysql_user_row = ttk.Frame(mysql_frame)
        mysql_user_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(mysql_user_row, text="User:", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(mysql_user_row, textvariable=mysql_user_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Password
        mysql_password_row = ttk.Frame(mysql_frame)
        mysql_password_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(mysql_password_row, text="Password:", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(mysql_password_row, textvariable=mysql_password_var, width=40, show="*").pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Database
        mysql_database_row = ttk.Frame(mysql_frame)
        mysql_database_row.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(mysql_database_row, text="Database:", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(mysql_database_row, textvariable=mysql_database_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Test Connection Button
        mysql_test_frame = ttk.Frame(mysql_frame)
        mysql_test_frame.pack(fill=tk.X)
        mysql_test_button = ttk.Button(mysql_test_frame, text="Test Connection",
                                       command=lambda: self.test_mysql_connection(
                                           mysql_host_var.get(),
                                           mysql_port_var.get(),
                                           mysql_user_var.get(),
                                           mysql_password_var.get(),
                                           mysql_database_var.get(),
                                           config_window
                                       ))
        mysql_test_button.pack(side=tk.LEFT)
        
        # ========== Buttons ==========
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        def validate_all():
            """Validate all configuration values."""
            # Validate replicate factor
            try:
                value = int(replicate_var.get())
                if value < 1:
                    messagebox.showerror("Invalid Value", "Replicate factor must be at least 1")
                    return False
            except ValueError:
                messagebox.showerror("Invalid Value", "Replicate factor must be an integer")
                return False
            
            # Validate MySQL port
            try:
                int(mysql_port_var.get())
            except ValueError:
                messagebox.showerror("Invalid Value", "MySQL port must be an integer")
                return False
            
            # Validate Qdrant port
            try:
                int(qdrant_port_var.get())
            except ValueError:
                messagebox.showerror("Invalid Value", "Qdrant port must be an integer")
                return False
            
            return True
        
        def save_config():
            """Save all configuration values to SQLite."""
            if not validate_all():
                return
            
            # Save replicate factor
            self.replicate_factor = int(replicate_var.get())
            ConfigService.set_int("replicate_factor", self.replicate_factor)
            
            # Save Qdrant settings
            ConfigService.set("QDRANT_URL", qdrant_url_var.get())
            ConfigService.set("QDRANT_PORT", qdrant_port_var.get())
            ConfigService.set("QDRANT_API_KEY", qdrant_api_key_var.get())
            ConfigService.set("QDRANT_HTTPS", "true" if qdrant_https_var.get() else "false")
            
            # Save MySQL settings
            ConfigService.set("MYSQL_HOST", mysql_host_var.get())
            ConfigService.set("MYSQL_PORT", mysql_port_var.get())
            ConfigService.set("MYSQL_USER", mysql_user_var.get())
            ConfigService.set("MYSQL_PASSWORD", mysql_password_var.get())
            ConfigService.set("MYSQL_DATABASE", mysql_database_var.get())
            
            messagebox.showinfo("Success", "Configuration saved successfully!\n\nNote: Qdrant and MySQL connections will use new settings on next initialization.")
            config_window.destroy()
        
        def cancel_config():
            config_window.destroy()
        
        ttk.Button(button_frame, text="Save", command=save_config, width=12).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=cancel_config, width=12).pack(side=tk.RIGHT)
    
    def test_qdrant_connection(self, url: str, port: str, api_key: str, https: bool, parent_window):
        """Test Qdrant connection with provided settings."""
        def test_in_thread():
            try:
                # Validate port
                try:
                    port_int = int(port)
                except ValueError:
                    parent_window.after(0, lambda: messagebox.showerror(
                        "Connection Test Failed",
                        "Invalid port number. Port must be an integer.",
                        parent=parent_window
                    ))
                    return
                
                # Create a temporary client to test connection
                from qdrant_client import QdrantClient
                
                test_client = QdrantClient(
                    url=url,
                    port=port_int,
                    api_key=api_key if api_key else None,
                    https=https,
                    timeout=10  # Short timeout for testing
                )
                
                # Try to get collections (simple operation to test connection)
                try:
                    collections = test_client.get_collections()
                    test_client.close()
                    
                    # Success
                    parent_window.after(0, lambda: messagebox.showinfo(
                        "Connection Test Successful",
                        f"Successfully connected to Qdrant!\n\n"
                        f"URL: {url}\n"
                        f"Port: {port}\n"
                        f"HTTPS: {https}\n"
                        f"Found {len(collections.collections)} collection(s).",
                        parent=parent_window
                    ))
                except Exception as e:
                    test_client.close()
                    raise e
                    
            except Exception as e:
                error_msg = str(e)
                parent_window.after(0, lambda: messagebox.showerror(
                    "Connection Test Failed",
                    f"Failed to connect to Qdrant:\n\n{error_msg}\n\n"
                    f"Please check:\n"
                    f"- URL and port are correct\n"
                    f"- Qdrant server is running\n"
                    f"- Network connectivity\n"
                    f"- API key (if required)",
                    parent=parent_window
                ))
        
        # Run test in separate thread to avoid blocking UI
        thread = threading.Thread(target=test_in_thread, daemon=True)
        thread.start()
    
    def test_mysql_connection(self, host: str, port: str, user: str, password: str, database: str, parent_window):
        """Test MySQL connection with provided settings."""
        def test_in_thread():
            try:
                # Validate port
                try:
                    port_int = int(port)
                except ValueError:
                    parent_window.after(0, lambda: messagebox.showerror(
                        "Connection Test Failed",
                        "Invalid port number. Port must be an integer.",
                        parent=parent_window
                    ))
                    return
                
                # Try to import mysql.connector
                try:
                    import mysql.connector
                    from mysql.connector import Error
                except ImportError:
                    parent_window.after(0, lambda: messagebox.showerror(
                        "Connection Test Failed",
                        "mysql-connector-python is not installed.\n\n"
                        "Install it with: pip install mysql-connector-python>=8.2.0",
                        parent=parent_window
                    ))
                    return
                
                # Try to connect
                connection = None
                try:
                    connection = mysql.connector.connect(
                        host=host,
                        port=port_int,
                        user=user,
                        password=password,
                        database=database,
                        connection_timeout=5  # Short timeout for testing
                    )
                    
                    if connection.is_connected():
                        # Get server info
                        cursor = connection.cursor()
                        cursor.execute("SELECT VERSION()")
                        version = cursor.fetchone()[0]
                        cursor.close()
                        connection.close()
                        
                        # Success
                        parent_window.after(0, lambda: messagebox.showinfo(
                            "Connection Test Successful",
                            f"Successfully connected to MySQL!\n\n"
                            f"Host: {host}\n"
                            f"Port: {port}\n"
                            f"Database: {database}\n"
                            f"User: {user}\n"
                            f"MySQL Version: {version}",
                            parent=parent_window
                        ))
                        
                except Error as e:
                    if connection and connection.is_connected():
                        connection.close()
                    raise e
                    
            except Exception as e:
                error_msg = str(e)
                parent_window.after(0, lambda: messagebox.showerror(
                    "Connection Test Failed",
                    f"Failed to connect to MySQL:\n\n{error_msg}\n\n"
                    f"Please check:\n"
                    f"- Host and port are correct\n"
                    f"- MySQL server is running\n"
                    f"- Username and password are correct\n"
                    f"- Database exists\n"
                    f"- Network connectivity",
                    parent=parent_window
                ))
        
        # Run test in separate thread to avoid blocking UI
        thread = threading.Thread(target=test_in_thread, daemon=True)
        thread.start()
        
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
        
        self.save_check = ttk.Checkbutton(options_frame, text="Save to MySQL (--save)", 
                                         variable=self.save_var)
        self.save_check.pack(anchor=tk.W, pady=3)
                       
        self.latest_check = ttk.Checkbutton(options_frame, text="Use latest from MySQL (--latest)", 
                                           variable=self.latest_var)
        self.latest_check.pack(anchor=tk.W, pady=3)
        
        self.last_mysql_check = ttk.Checkbutton(options_frame, text="Load from MySQL (-ml)", 
                                               variable=self.last_mongo_var)
        self.last_mysql_check.pack(anchor=tk.W, pady=3)
        
        # 5. Execute Button
        self.execute_button = ttk.Button(left_panel, text="▶ Execute Operation", 
                                        command=self.execute_operation, width=25)
        self.execute_button.pack(pady=(10, 0))
        
        # ========== RIGHT PANEL - OUTPUT ==========
        
        output_frame = ttk.LabelFrame(right_panel, text="Output & Results", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        # Progress bar (shown during operations)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(output_frame, variable=self.progress_var, 
                                            maximum=100, mode='determinate')
        # Don't pack initially - will be shown when needed
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(output_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Results (Treeview + Summary)
        results_frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(results_frame, text="📊 Results")
        
        # Summary panel at top
        summary_frame = ttk.LabelFrame(results_frame, text="Summary", padding="10")
        summary_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.summary_label = ttk.Label(summary_frame, text="No data available", 
                                       font=("Segoe UI", 10))
        self.summary_label.pack(anchor=tk.W)
        
        # Export buttons
        export_frame = ttk.Frame(summary_frame)
        export_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(export_frame, text="📋 Copy to Clipboard", 
                  command=self.copy_to_clipboard, width=20).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(export_frame, text="💾 Export CSV", 
                  command=self.export_csv, width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(export_frame, text="💾 Export JSON", 
                  command=self.export_json, width=15).pack(side=tk.LEFT)
        
        # Treeview for shard display
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars for treeview
        tree_scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        
        # Create treeview
        columns = ("Peer ID", "Peer URI", "Shard ID", "Points", "State")
        self.shard_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                       yscrollcommand=tree_scroll_y.set,
                                       xscrollcommand=tree_scroll_x.set)
        
        # Configure scrollbars
        tree_scroll_y.config(command=self.shard_tree.yview)
        tree_scroll_x.config(command=self.shard_tree.xview)
        
        # Configure columns
        self.shard_tree.heading("Peer ID", text="Peer ID", command=lambda: self.sort_tree("Peer ID"))
        self.shard_tree.heading("Peer URI", text="Peer URI", command=lambda: self.sort_tree("Peer URI"))
        self.shard_tree.heading("Shard ID", text="Shard ID", command=lambda: self.sort_tree("Shard ID"))
        self.shard_tree.heading("Points", text="Points", command=lambda: self.sort_tree("Points"))
        self.shard_tree.heading("State", text="State", command=lambda: self.sort_tree("State"))
        
        self.shard_tree.column("Peer ID", width=80, anchor=tk.CENTER)
        self.shard_tree.column("Peer URI", width=200, anchor=tk.W)
        self.shard_tree.column("Shard ID", width=80, anchor=tk.CENTER)
        self.shard_tree.column("Points", width=120, anchor=tk.E)
        self.shard_tree.column("State", width=120, anchor=tk.CENTER)
        
        # Grid layout for treeview and scrollbars
        self.shard_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind click events for toggle selection
        # Use ButtonRelease-1 to check selection after Treeview processes the click
        self.shard_tree.bind("<Button-1>", self.on_tree_click_down)
        self.shard_tree.bind("<ButtonRelease-1>", self.on_tree_click_up)
        self.shard_tree.bind("<Double-1>", self.on_tree_double_click)
        
        # Track selection before click for toggle detection
        self.selection_before_click = set()
        
        # Configure treeview tags for state colors
        self.shard_tree.tag_configure("active", background="#d4edda")
        self.shard_tree.tag_configure("dead", background="#f8d7da")
        self.shard_tree.tag_configure("partial", background="#fff3cd")
        self.shard_tree.tag_configure("replica", background="#d1ecf1")
        
        # Tab 2: Logs
        logs_frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(logs_frame, text="📝 Logs")
        
        # Output text area for logs
        self.output_text = scrolledtext.ScrolledText(logs_frame, wrap=tk.WORD, 
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
        
        # Track sort direction
        self.sort_reverse = {}
        for col in columns:
            self.sort_reverse[col] = False

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
        
        # Enable/disable options based on operation type
        # --save: Available for all operations
        self.save_check.config(state=tk.NORMAL)
        
        # --latest: Only for move and replicate
        if operation in ["move", "replicate"]:
            self.latest_check.config(state=tk.NORMAL)
        else:
            self.latest_check.config(state=tk.DISABLED)
            self.latest_var.set(False)
        
        # -ml (Load from MySQL): Only for list
        if operation == "list":
            self.last_mysql_check.config(state=tk.NORMAL)
        else:
            self.last_mysql_check.config(state=tk.DISABLED)
            self.last_mongo_var.set(False)
        
        # Show relevant parameter frames based on operation
        if operation == "list":
            # No extra parameters needed
            pass
        elif operation in ["move", "replicate"]:
            self.peer_frame.pack(fill=tk.X, pady=5)
            self.method_frame.pack(fill=tk.X, pady=5)
        elif operation == "abort":
            self.peer_frame.pack(fill=tk.X, pady=5)
            self.shard_frame.pack(fill=tk.X, pady=5)
            self.latest_check.config(state=tk.DISABLED)
            self.last_mysql_check.config(state=tk.DISABLED)

    def log_output(self, text: str, tag: str = None):
        """Add text to output area with optional formatting."""
        self.output_text.insert(tk.END, text + "\n", tag)
        self.output_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_output(self):
        """Clear output area."""
        self.output_text.delete(1.0, tk.END)
        # Clear treeview
        for item in self.shard_tree.get_children():
            self.shard_tree.delete(item)
        # Clear summary
        self.summary_label.config(text="No data available")
        # Clear stored data
        self.current_peer_shards = None
        self.current_peer_uris = None
    
    def show_progress(self, show: bool = True):
        """Show or hide progress bar."""
        if show:
            self.progress_bar.pack(fill=tk.X, pady=(5, 0), before=self.notebook)
        else:
            self.progress_bar.pack_forget()
    
    def update_progress(self, value: float, maximum: float = 100.0):
        """Update progress bar."""
        percentage = (value / maximum) * 100 if maximum > 0 else 0
        self.progress_var.set(percentage)
        self.root.update_idletasks()
    
    def sort_tree(self, column: str):
        """Sort treeview by column."""
        items = [(self.shard_tree.set(item, column), item) for item in self.shard_tree.get_children('')]
        
        # Determine sort direction
        try:
            # Try numeric sort
            items.sort(key=lambda t: float(t[0]) if t[0] else 0, reverse=self.sort_reverse[column])
        except ValueError:
            # String sort
            items.sort(key=lambda t: t[0].lower(), reverse=self.sort_reverse[column])
        
        # Rearrange items
        for index, (val, item) in enumerate(items):
            self.shard_tree.move(item, '', index)
        
        # Toggle sort direction
        self.sort_reverse[column] = not self.sort_reverse[column]
    
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
                               "-ml (Load from MySQL) can only be used with List operation")
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
    
    def ensure_mysql_initialized(self):
        """Ensure MySQL is initialized if needed."""
        if self.mysql_service is None:
            if self.save_var.get() or self.last_mongo_var.get() or self.latest_var.get():
                self.log_output("🔌 Initializing MySQL connection...", "info")
                # Use ConfigService values for MySQL connection
                from qdrant_distributed.config import get_mysql_host, get_mysql_port, get_mysql_user, get_mysql_password, get_mysql_database
                MySQLManager.initialize(
                    host=get_mysql_host(),
                    port=get_mysql_port(),
                    user=get_mysql_user(),
                    password=get_mysql_password(),
                    database=get_mysql_database()
                )
                self.mysql_service = MySQLService()
                self.log_output(f"✅ MySQL connection initialized (Host: {get_mysql_host()}, Database: {get_mysql_database()})", "success")
    
    def initialize_services(self):
        """Initialize Qdrant and MySQL services."""
        if not self.is_initialized:
            self.log_output("🔌 Initializing Qdrant client...", "info")
            # Use ConfigService values for Qdrant connection
            from qdrant_distributed.config import get_qdrant_url, get_qdrant_port, get_qdrant_api_key, get_qdrant_https
            qdrant_url = get_qdrant_url()
            qdrant_port = get_qdrant_port()
            qdrant_api_key = get_qdrant_api_key()
            qdrant_https = get_qdrant_https(default=True)
            
            QdrantClientManager.initialize(
                url=qdrant_url,
                port=qdrant_port,
                api_key=qdrant_api_key
            )
            self.log_output(f"✅ Qdrant client initialized (URL: {qdrant_url}, Port: {qdrant_port})", "success")
            
            # Initialize operations
            self.shard_ops = ShardOperations()
            self.cluster_ops = ClusterOperations()
            
            self.is_initialized = True
        
        # Always check if MySQL is needed (in case flags changed)
        self.ensure_mysql_initialized()
    
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
            
            self.update_progress(10)
            self.initialize_services()
            self.update_progress(20)
            
            if operation == "list":
                self.execute_list_operation(collection, timeout)
            elif operation == "move":
                self.execute_move_operation(collection, timeout)
            elif operation == "replicate":
                self.execute_replicate_operation(collection, timeout)
            elif operation == "abort":
                self.execute_abort_operation(collection, timeout)
            
            self.update_progress(90)
            
            # Get captured output
            output = sys.stdout.getvalue()
            if output:
                self.log_output(output)
            
            sys.stdout = old_stdout
            
            self.update_progress(100)
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
            self.show_progress(False)
            self.update_progress(0)
    
    def execute_list_operation(self, collection: str, timeout: int):
        """Execute list shards operation."""
        self.log_output("📋 Listing all local shards from each peer in the cluster\n", "info")
        self.update_progress(30)
        
        if self.last_mongo_var.get():
            self.ensure_mysql_initialized()
            if self.mysql_service is None:
                raise ValueError("MySQL service not initialized. Please check MySQL connection settings.")
            self.update_progress(50)
            # Fetch once and reuse to avoid duplicate queries
            latest_doc = self.mysql_service.get_latest_peers()
            peer_shards = self.mysql_service.get_latest_peers_as_dict(latest_doc)
            peer_uris = self.mysql_service.get_latest_peer_uris(latest_doc)
            self.update_progress(80)
            self.display_shard_list(peer_shards, peer_uris)
        else:
            self.update_progress(40)
            peer_shards = self.cluster_ops.list_all_shards(collection_name=collection, timeout=timeout)
            self.update_progress(60)
            
            # Get peer URIs
            from qdrant_distributed.client import ClusterClient
            cluster_client = ClusterClient()
            peers_dict, _ = cluster_client.get_peers(timeout)
            peer_uris = {int(pid): peer_data.get("uri", "") for pid, peer_data in peers_dict.items()}
            self.update_progress(70)
            
            self.display_shard_list(peer_shards, peer_uris)
            
            # Save to MySQL if requested
            if self.save_var.get():
                self.ensure_mysql_initialized()
                if self.mysql_service is None:
                    raise ValueError("MySQL service not initialized. Please check MySQL connection settings.")
                self.log_output("\n💾 Saving peer information to MySQL...", "info")
                peer_info_list = self.convert_peer_shards_to_peer_info(peer_shards, peers_dict)
                self.mysql_service.save_peers(peer_info_list)
                self.log_output("✓ Peer information saved to MySQL", "success")
    
    def get_selected_shard_ids(self, from_peer: int) -> List[int]:
        """Get selected shard IDs from the Treeview that belong to the specified peer."""
        selected_shard_ids = []
        selected_items = self.shard_tree.selection()
        
        for item in selected_items:
            item_peer_id = int(self.shard_tree.set(item, "Peer ID"))
            if item_peer_id == from_peer:
                shard_id = int(self.shard_tree.set(item, "Shard ID"))
                selected_shard_ids.append(shard_id)
        
        # Remove duplicates and sort
        return sorted(list(set(selected_shard_ids)))
    
    def count_shard_copies(self, all_shards: Dict[int, List[ShardInfo]], shard_id: int, exclude_peer_id: Optional[int] = None) -> int:
        """
        Count the number of copies of a shard across all peers.
        
        Args:
            all_shards: Dictionary mapping peer_id to list of ShardInfo objects
            shard_id: The shard ID to count copies for
            exclude_peer_id: Optional peer ID to exclude from the count (e.g., when moving from a peer)
        
        Returns:
            Number of copies of the shard across peers
        """
        count = 0
        for peer_id, shards in all_shards.items():
            if exclude_peer_id is not None and peer_id == exclude_peer_id:
                continue
            if any(shard.shard_id == shard_id for shard in shards):
                count += 1
        return count
    
    def validate_replicate_factor(self, all_shards: Dict[int, List[ShardInfo]], 
                                  shard_ids: List[int], from_peer_id: int, 
                                  to_peer_id: int, operation: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that replicating/moving shards won't exceed the replicate factor.
        
        Args:
            all_shards: Dictionary mapping peer_id to list of ShardInfo objects
            shard_ids: List of shard IDs to validate
            from_peer_id: Source peer ID
            to_peer_id: Destination peer ID
            operation: Operation type ("move" or "replicate")
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if destination peer already has any of these shards
        to_peer_shards = all_shards.get(to_peer_id, [])
        to_peer_shard_ids = {shard.shard_id for shard in to_peer_shards}
        
        for shard_id in shard_ids:
            # Skip if shard already exists in destination peer
            if shard_id in to_peer_shard_ids:
                continue
            
            if operation == "move":
                # For move: source peer loses the shard, destination peer gains it
                # Count copies excluding the source peer (since it will lose the shard)
                current_copies = self.count_shard_copies(all_shards, shard_id, exclude_peer_id=from_peer_id)
                # After move: destination will have it, so total copies = current_copies + 1
                # But we need to check if destination already has it (we already checked above, so it doesn't)
                # So after move, count will be current_copies + 1
                if current_copies + 1 > self.replicate_factor:
                    return False, f"Shard {shard_id} would have {current_copies + 1} copies after move, which exceeds the replicate factor ({self.replicate_factor}). Cannot move."
            else:  # replicate
                # For replicate: we're adding a new copy to destination
                # Count all current copies
                current_copies = self.count_shard_copies(all_shards, shard_id)
                # After replicate, count will be current_copies + 1
                if current_copies + 1 > self.replicate_factor:
                    return False, f"Shard {shard_id} would have {current_copies + 1} copies after replicate, which exceeds the replicate factor ({self.replicate_factor}). Cannot replicate."
        
        return True, None
    
    def execute_move_operation(self, collection: str, timeout: int):
        """Execute move shards operation."""
        from_peer = int(self.from_peer_var.get())
        to_peer = int(self.to_peer_var.get())
        method = self.method_var.get()
        
        # Get selected shard IDs from Treeview (only from from_peer)
        selected_shard_ids = self.get_selected_shard_ids(from_peer)
        
        if selected_shard_ids:
            self.log_output(f"🚀 Moving shards {selected_shard_ids} from peer {from_peer} to peer {to_peer}", "info")
        else:
            self.log_output(f"🚀 Moving all shards from peer {from_peer} to peer {to_peer}", "info")
        self.log_output(f"   Method: {method}\n", "info")
        self.update_progress(30)
        
        # Get shard information
        if self.latest_var.get():
            self.ensure_mysql_initialized()
            if self.mysql_service is None:
                raise ValueError("MySQL service not initialized. Please check MySQL connection settings.")
            self.log_output("📋 Getting shard information from MySQL (latest)...", "info")
            all_peer_shards = self.mysql_service.get_latest_peers_as_dict()
            self.log_output("✓ Retrieved peer information from MySQL\n", "success")
            self.update_progress(50)
        else:
            self.log_output("📋 Getting shard information from peers...", "info")
            all_peer_shards = self.cluster_ops.list_all_shards(collection_name=collection, timeout=timeout)
            self.log_output("")
            self.update_progress(50)
        
        # Validate replicate factor before executing move
        # Get shards that will actually be moved
        from_peer_shards = all_peer_shards.get(from_peer, [])
        to_peer_shards = all_peer_shards.get(to_peer, [])
        to_peer_shard_ids = {shard.shard_id for shard in to_peer_shards}
        
        # Determine which shards will be moved
        if selected_shard_ids:
            shards_to_move = [shard for shard in from_peer_shards 
                            if shard.shard_id in selected_shard_ids 
                            and shard.shard_id not in to_peer_shard_ids]
        else:
            shards_to_move = [shard for shard in from_peer_shards 
                            if shard.shard_id not in to_peer_shard_ids]
        
        if shards_to_move:
            shard_ids_to_validate = [shard.shard_id for shard in shards_to_move]
            is_valid, error_msg = self.validate_replicate_factor(
                all_peer_shards, shard_ids_to_validate, from_peer, to_peer, "move"
            )
            if not is_valid:
                raise ValueError(error_msg)
        
        # Execute move
        self.update_progress(60)
        self.shard_ops.move_all(
            collection_name=collection,
            all_shards=all_peer_shards,
            from_peer_id=from_peer,
            to_peer_id=to_peer,
            method=ShardTransferMethod(method),
            timeout=timeout,
            shard_ids=selected_shard_ids if selected_shard_ids else None
        )
        self.update_progress(85)
    
    def execute_replicate_operation(self, collection: str, timeout: int):
        """Execute replicate shards operation."""
        from_peer = int(self.from_peer_var.get())
        to_peer = int(self.to_peer_var.get())
        method = self.method_var.get()
        
        # Get selected shard IDs from Treeview (only from from_peer)
        selected_shard_ids = self.get_selected_shard_ids(from_peer)
        
        if selected_shard_ids:
            self.log_output(f"🔁 Replicating shards {selected_shard_ids} from peer {from_peer} to peer {to_peer}", "info")
        else:
            self.log_output(f"🔁 Replicating all shards from peer {from_peer} to peer {to_peer}", "info")
        self.log_output(f"   Method: {method}\n", "info")
        self.update_progress(30)
        
        # Get shard information
        if self.latest_var.get():
            self.ensure_mysql_initialized()
            if self.mysql_service is None:
                raise ValueError("MySQL service not initialized. Please check MySQL connection settings.")
            self.log_output("📋 Getting shard information from MySQL (latest)...", "info")
            all_peer_shards = self.mysql_service.get_latest_peers_as_dict()
            self.log_output("✓ Retrieved peer information from MySQL\n", "success")
            self.update_progress(50)
        else:
            self.log_output("📋 Getting shard information from peers...", "info")
            all_peer_shards = self.cluster_ops.list_all_shards(collection_name=collection, timeout=timeout)
            self.log_output("")
            self.update_progress(50)
        
        # Validate replicate factor before executing replicate
        # Get shards that will actually be replicated
        from_peer_shards = all_peer_shards.get(from_peer, [])
        to_peer_shards = all_peer_shards.get(to_peer, [])
        to_peer_shard_ids = {shard.shard_id for shard in to_peer_shards}
        
        # Determine which shards will be replicated
        if selected_shard_ids:
            shards_to_replicate = [shard for shard in from_peer_shards 
                                 if shard.shard_id in selected_shard_ids 
                                 and shard.shard_id not in to_peer_shard_ids]
        else:
            shards_to_replicate = [shard for shard in from_peer_shards 
                                 if shard.shard_id not in to_peer_shard_ids]
        
        if shards_to_replicate:
            shard_ids_to_validate = [shard.shard_id for shard in shards_to_replicate]
            is_valid, error_msg = self.validate_replicate_factor(
                all_peer_shards, shard_ids_to_validate, from_peer, to_peer, "replicate"
            )
            if not is_valid:
                raise ValueError(error_msg)
        
        # Execute replicate
        self.update_progress(60)
        self.shard_ops.replicate_all(
            collection_name=collection,
            all_shards=all_peer_shards,
            from_peer_id=from_peer,
            to_peer_id=to_peer,
            method=ShardTransferMethod(method),
            timeout=timeout,
            shard_ids=selected_shard_ids if selected_shard_ids else None
        )
        self.update_progress(85)
    
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
        """Display shard list in treeview and update summary."""
        # Store for export
        self.current_peer_shards = peer_shards
        self.current_peer_uris = peer_uris
        
        # Switch to Results tab
        self.notebook.select(0)
        
        # Clear existing treeview items
        for item in self.shard_tree.get_children():
            self.shard_tree.delete(item)
        
        # Log to text area
        self.log_output("=" * 80, "header")
        self.log_output("✅ Successfully retrieved shard information from all peers!", "success")
        self.log_output("=" * 80, "header")
        self.log_output("")
        
        if not peer_shards:
            self.log_output("⚠️  No peers found or no shard information available", "warning")
            self.summary_label.config(text="⚠️  No peers found or no shard information available")
            return
        
        total_shards = 0
        total_points = 0
        
        # Populate treeview
        for peer_id, shards in sorted(peer_shards.items()):
            uri = peer_uris.get(peer_id, "") if peer_uris else ""
            
            # Log to text area
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
                    
                    # Add to treeview
                    tag = self._get_state_tag(state)
                    self.shard_tree.insert('', tk.END, values=(
                        peer_id,
                        uri,
                        shard_id,
                        f"{points_count:,}",
                        state
                    ), tags=(tag,))
                    
                    # Log to text area
                    self.log_output(f"   ├─ Shard {shard_id}")
                    self.log_output(f"   │  ├─ Points: {points_count:,}")
                    self.log_output(f"   │  └─ State: {state}")
            
            self.log_output("")
        
        # Update summary
        summary_text = (
            f"📊 Total Peers: {len(peer_shards)} | "
            f"Total Shards: {total_shards} | "
            f"Total Local points: {total_points:,}"
        )
        self.summary_label.config(text=summary_text)
        
        # Log summary
        self.log_output("=" * 80, "header")
        self.log_output(f"📊 Summary:", "header")
        self.log_output(f"   Total Peers: {len(peer_shards)}")
        self.log_output(f"   Total Local Shards: {total_shards}")
        self.log_output(f"   Total Local points: {total_points:,}")
        self.log_output("=" * 80, "header")
    
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
    
    def on_tree_click_down(self, event):
        """Store selection state before click to detect toggle."""
        # Store current selection before the click is processed
        self.selection_before_click = set(self.shard_tree.selection())
    
    def on_tree_click_up(self, event):
        """Handle mouse button release to toggle selection."""
        # Check if Ctrl or Cmd key is held (for multi-select)
        is_multi_select = (event.state & 0x4) != 0 or (event.state & 0x20000) != 0  # Ctrl or Cmd
        
        # Get the item under the cursor
        item = self.shard_tree.identify_row(event.y)
        if not item:
            # Clicked on empty space - selection already cleared by Treeview
            self.selection_before_click = set()
            return
        
        # Get current selection after click
        current_selection = set(self.shard_tree.selection())
        
        # If item was selected before click and is still selected now, toggle it off
        if item in self.selection_before_click and item in current_selection:
            # Only toggle if not in multi-select mode (Ctrl/Cmd)
            if not is_multi_select:
                # If it's the only selected item, deselect it
                if len(current_selection) == 1 and item in current_selection:
                    self.shard_tree.selection_remove(item)
                # If multiple items are selected and this was one of them, allow toggle
                elif item in current_selection and len(current_selection) > len(self.selection_before_click):
                    # New item was added - don't toggle
                    pass
                elif item in current_selection:
                    # Same item clicked - toggle it off
                    self.shard_tree.selection_remove(item)
    
    def on_tree_double_click(self, event):
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
                # Copy to clipboard
                self.root.clipboard_clear()
                self.root.clipboard_append(str(peer_id))
                # Show brief status message
                original_status = self.status_label.cget("text")
                self.set_status(f"Copied Peer ID {peer_id} to clipboard")
                # Reset status after 2 seconds
                self.root.after(2000, lambda: self.set_status(original_status))
    
    def copy_to_clipboard(self):
        """Copy shard data to clipboard."""
        if not self.current_peer_shards:
            messagebox.showinfo("No Data", "No shard data to copy. Please run a list operation first.")
            return
        
        try:
            lines = []
            lines.append("Peer ID\tPeer URI\tShard ID\tPoints\tState")
            for peer_id, shards in sorted(self.current_peer_shards.items()):
                uri = self.current_peer_uris.get(peer_id, "") if self.current_peer_uris else ""
                if not shards:
                    lines.append(f"{peer_id}\t{uri}\t-\t-\t-")
                else:
                    for shard in shards:
                        lines.append(f"{peer_id}\t{uri}\t{shard.shard_id}\t{shard.points_count}\t{shard.state.value}")
            
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(lines))
            messagebox.showinfo("Success", "Shard data copied to clipboard!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy to clipboard: {e}")
    
    def export_csv(self):
        """Export shard data to CSV file."""
        if not self.current_peer_shards:
            messagebox.showinfo("No Data", "No shard data to export. Please run a list operation first.")
            return
        
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not filename:
                return
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Peer ID", "Peer URI", "Shard ID", "Points", "State"])
                
                for peer_id, shards in sorted(self.current_peer_shards.items()):
                    uri = self.current_peer_uris.get(peer_id, "") if self.current_peer_uris else ""
                    if not shards:
                        writer.writerow([peer_id, uri, "", "", ""])
                    else:
                        for shard in shards:
                            writer.writerow([
                                peer_id,
                                uri,
                                shard.shard_id,
                                shard.points_count,
                                shard.state.value
                            ])
            
            messagebox.showinfo("Success", f"Data exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {e}")
    
    def export_json(self):
        """Export shard data to JSON file."""
        if not self.current_peer_shards:
            messagebox.showinfo("No Data", "No shard data to export. Please run a list operation first.")
            return
        
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if not filename:
                return
            
            data = {
                "peers": []
            }
            
            for peer_id, shards in sorted(self.current_peer_shards.items()):
                uri = self.current_peer_uris.get(peer_id, "") if self.current_peer_uris else ""
                peer_data = {
                    "peer_id": peer_id,
                    "uri": uri,
                    "shards": [shard.to_dict() for shard in shards] if shards else []
                }
                data["peers"].append(peer_data)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            messagebox.showinfo("Success", f"Data exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export JSON: {e}")
    
    def execute_operation(self):
        """Execute button click handler."""
        if not self.validate_inputs():
            return
        
        self.clear_output()
        self.set_status("Running operation...")
        self.execute_button.config(state=tk.DISABLED)
        self.show_progress(True)
        self.update_progress(0)
        
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
