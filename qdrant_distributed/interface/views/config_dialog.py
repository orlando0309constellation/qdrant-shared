"""
Configuration Dialog View - Settings dialog window.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from qdrant_client import QdrantClient
from qdrant_distributed.interface.services.app_state import AppState
from qdrant_distributed.interface.controllers.service_controller import ServiceController
from qdrant_distributed.services.config_service import ConfigService


class ConfigDialog:
    """Configuration dialog window."""
    
    def __init__(self, parent, app_state: AppState, service_controller: ServiceController):
        self.parent = parent
        self.app_state = app_state
        self.service_controller = service_controller
        
        self.window = tk.Toplevel(parent)
        self.window.title("Configuration Settings")
        self.window.geometry("650x700")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()
        
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
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Configuration Settings", 
                               font=("Segoe UI", 14, "bold"))
        title_label.pack(pady=(0, 15))
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Tab 1: Replication
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
        replicate_var = tk.StringVar(value=str(self.app_state.replicate_factor))
        ttk.Entry(replicate_row, textvariable=replicate_var, width=15).pack(side=tk.LEFT)
        
        # Tab 2: Qdrant
        qdrant_tab = ttk.Frame(notebook, padding="15")
        notebook.add(qdrant_tab, text="Qdrant")
        
        qdrant_frame = ttk.LabelFrame(qdrant_tab, text="Qdrant Connection Settings", padding="15")
        qdrant_frame.pack(fill=tk.X, pady=(0, 10))
        
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
                                        command=lambda: self._test_qdrant_connection(
                                            qdrant_url_var.get(),
                                            qdrant_port_var.get(),
                                            qdrant_api_key_var.get(),
                                            qdrant_https_var.get()
                                        ))
        qdrant_test_button.pack(side=tk.LEFT)
        
        # Tab 3: MySQL
        mysql_tab = ttk.Frame(notebook, padding="15")
        notebook.add(mysql_tab, text="MySQL")
        
        mysql_frame = ttk.LabelFrame(mysql_tab, text="MySQL Connection Settings", padding="15")
        mysql_frame.pack(fill=tk.X, pady=(0, 10))
        
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
                                       command=lambda: self._test_mysql_connection(
                                           mysql_host_var.get(),
                                           mysql_port_var.get(),
                                           mysql_user_var.get(),
                                           mysql_password_var.get(),
                                           mysql_database_var.get()
                                       ))
        mysql_test_button.pack(side=tk.LEFT)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        def validate_all():
            try:
                value = int(replicate_var.get())
                if value < 1:
                    messagebox.showerror("Invalid Value", "Replicate factor must be at least 1")
                    return False
            except ValueError:
                messagebox.showerror("Invalid Value", "Replicate factor must be an integer")
                return False
            
            try:
                int(mysql_port_var.get())
            except ValueError:
                messagebox.showerror("Invalid Value", "MySQL port must be an integer")
                return False
            
            try:
                int(qdrant_port_var.get())
            except ValueError:
                messagebox.showerror("Invalid Value", "Qdrant port must be an integer")
                return False
            
            return True
        
        def save_config():
            if not validate_all():
                return
            
            # Store old Qdrant config to check if it changed
            old_qdrant_url = ConfigService.get("QDRANT_URL")
            old_qdrant_port = ConfigService.get("QDRANT_PORT")
            old_qdrant_api_key = ConfigService.get("QDRANT_API_KEY")
            old_qdrant_https = ConfigService.get("QDRANT_HTTPS")
            
            self.app_state.update_replicate_factor(int(replicate_var.get()))
            
            ConfigService.set("QDRANT_URL", qdrant_url_var.get())
            ConfigService.set("QDRANT_PORT", qdrant_port_var.get())
            ConfigService.set("QDRANT_API_KEY", qdrant_api_key_var.get())
            ConfigService.set("QDRANT_HTTPS", "true" if qdrant_https_var.get() else "false")
            
            ConfigService.set("MYSQL_HOST", mysql_host_var.get())
            ConfigService.set("MYSQL_PORT", mysql_port_var.get())
            ConfigService.set("MYSQL_USER", mysql_user_var.get())
            ConfigService.set("MYSQL_PASSWORD", mysql_password_var.get())
            ConfigService.set("MYSQL_DATABASE", mysql_database_var.get())
            
            # Check if Qdrant configuration changed
            qdrant_config_changed = (
                old_qdrant_url != qdrant_url_var.get() or
                old_qdrant_port != qdrant_port_var.get() or
                old_qdrant_api_key != qdrant_api_key_var.get() or
                old_qdrant_https != ("true" if qdrant_https_var.get() else "false")
            )
            
            # Reset Qdrant clients if configuration changed
            if qdrant_config_changed:
                self.service_controller.reset_qdrant()
            
            messagebox.showinfo("Success", "Configuration saved successfully!\n\n" + 
                              ("Qdrant connections have been reset and will use new settings immediately." if qdrant_config_changed 
                               else "Qdrant and MySQL connections will use new settings on next initialization."))
            self.window.destroy()
        
        def cancel_config():
            self.window.destroy()
        
        ttk.Button(button_frame, text="Save", command=save_config, width=12).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=cancel_config, width=12).pack(side=tk.RIGHT)
    
    def _test_qdrant_connection(self, url: str, port: str, api_key: str, https: bool):
        """Test Qdrant connection."""
        def test_in_thread():
            try:
                scheme = "https" if https else "http"
                client_url = f"{scheme}://{url}:{port}"
                client = QdrantClient(url=client_url, api_key=api_key if api_key else None)
                client.get_collections()
                self.window.after(0, lambda: messagebox.showinfo("Connection Test", "Successfully connected to Qdrant!", parent=self.window))
            except Exception as e:
                error_msg = str(e)
                self.window.after(0, lambda: messagebox.showerror("Connection Test Failed", f"Failed to connect to Qdrant:\n\n{error_msg}", parent=self.window))
        
        thread = threading.Thread(target=test_in_thread, daemon=True)
        thread.start()
    
    def _test_mysql_connection(self, host: str, port: str, user: str, password: str, database: str):
        """Test MySQL connection."""
        def test_in_thread():
            try:
                import mysql.connector
                conn = mysql.connector.connect(
                    host=host,
                    port=int(port),
                    user=user,
                    password=password,
                    database=database
                )
                cursor = conn.cursor()
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()
                cursor.close()
                conn.close()
                self.window.after(0, lambda: messagebox.showinfo("Connection Test", f"Successfully connected to MySQL!\n\nVersion: {version[0]}", parent=self.window))
            except ImportError:
                self.window.after(0, lambda: messagebox.showerror("Connection Test Failed", "mysql-connector-python is not installed.\n\nPlease install it using: pip install mysql-connector-python", parent=self.window))
            except Exception as e:
                error_msg = str(e)
                self.window.after(0, lambda: messagebox.showerror("Connection Test Failed", f"Failed to connect to MySQL:\n\n{error_msg}", parent=self.window))
        
        thread = threading.Thread(target=test_in_thread, daemon=True)
        thread.start()

