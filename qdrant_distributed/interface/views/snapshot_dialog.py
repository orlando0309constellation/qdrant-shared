"""
Snapshot Management Dialog - Manage Qdrant snapshots.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any
from qdrant_distributed.services.config_service import ConfigService
from qdrant_distributed.services.snapshot_service import SnapshotService
from qdrant_distributed.interface.widgets.log_viewer import LogViewer


class SnapshotDialog:
    """Dialog for managing Qdrant snapshots."""
    
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("Snapshot Management")
        self.window.geometry("700x500")
        self.window.resizable(True, True)
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
        title_label = ttk.Label(main_frame, text="Snapshot Management", 
                               font=("Segoe UI", 14, "bold"))
        title_label.pack(pady=(0, 15))
        
        # Description
        desc_label = ttk.Label(main_frame, 
                              text="Configured snapshot URLs. Double-click a URL to manage snapshots, or use the 'More' button.",
                              wraplength=650, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W, pady=(0, 10))
        
        # List frame with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Treeview for URLs
        columns = ("url", "port", "https")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)
        tree.heading("url", text="URL")
        tree.heading("port", text="Port")
        tree.heading("https", text="HTTPS")
        tree.column("url", width=300)
        tree.column("port", width=100)
        tree.column("https", width=80)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click to open snapshot management dialog
        tree.bind("<Double-1>", lambda e: self._on_double_click())
        
        self.tree = tree
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="More...", command=self._show_more_menu).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Refresh", command=self._refresh_list).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT)
        
        # Load URLs
        self._refresh_list()
    
    def _refresh_list(self):
        """Refresh the list of snapshot URLs."""
        self.tree.delete(*self.tree.get_children())
        urls = ConfigService.get_snapshot_urls()
        
        for url_config in urls:
            url = url_config.get("url", "")
            port = url_config.get("port", "")
            https = "Yes" if url_config.get("https", False) else "No"
            self.tree.insert("", tk.END, values=(url, port, https), tags=(url, port, str(url_config.get("https", False))))
    
    def _get_selected_url(self) -> Optional[Dict[str, Any]]:
        """Get the selected URL configuration."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a URL from the list.", parent=self.window)
            return None
        
        item = self.tree.item(selection[0])
        values = item["values"]
        tags = item["tags"]
        
        if len(values) >= 3 and len(tags) >= 3:
            return {
                "url": values[0],
                "port": values[1],
                "https": tags[2].lower() == "true"
            }
        return None
    
    def _get_api_key(self) -> Optional[str]:
        """Get API key from configuration."""
        return ConfigService.get("QDRANT_API_KEY") or None
    
    def _on_double_click(self):
        """Handle double-click on URL to open snapshot management dialog."""
        url_config = self._get_selected_url()
        if url_config:
            SnapshotManagementDialog(self.window, url_config)
    
    def _show_more_menu(self):
        """Show context menu for selected URL."""
        url_config = self._get_selected_url()
        if not url_config:
            return
        
        # Create context menu
        menu = tk.Menu(self.window, tearoff=0)
        
        # Create Snapshot submenu
        create_menu = tk.Menu(menu, tearoff=0)
        create_menu.add_command(label="Collection...", command=lambda: self._create_collection_snapshot(url_config))
        create_menu.add_command(label="Cluster", command=lambda: self._create_cluster_snapshot(url_config))
        menu.add_cascade(label="Create Snapshot", menu=create_menu)
        
        menu.add_command(label="Recover Snapshot", command=lambda: self._recover_snapshot(url_config))
        menu.add_command(label="Delete Snapshot", command=lambda: self._delete_snapshot(url_config))
        
        # Show menu at cursor position
        try:
            menu.tk_popup(self.window.winfo_pointerx(), self.window.winfo_pointery())
        finally:
            menu.grab_release()
    
    def _create_collection_snapshot(self, url_config: Dict[str, Any]):
        """Open dialog to create collection snapshot."""
        # Open the tabbed dialog instead
        SnapshotManagementDialog(self.window, url_config)
    
    def _show_collection_dialog(self, url_config: Dict[str, Any], collections: List[str]):
        """Show dialog to select collection and create snapshot."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Create Collection Snapshot")
        dialog.geometry("400x200")
        dialog.transient(self.window)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Select Collection:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        collection_var = tk.StringVar()
        collection_combo = ttk.Combobox(main_frame, textvariable=collection_var, values=collections, state="readonly", width=40)
        collection_combo.pack(fill=tk.X, pady=(0, 20))
        
        if collections:
            collection_combo.current(0)
        
        def create_snapshot():
            collection_name = collection_var.get()
            if not collection_name:
                messagebox.showwarning("No Collection", "Please select a collection.", parent=dialog)
                return
            
            dialog.destroy()
            
            def create():
                try:
                    api_key = self._get_api_key()
                    result = SnapshotService.create_collection_snapshot(
                        url_config["url"],
                        url_config["port"],
                        url_config["https"],
                        api_key,
                        collection_name
                    )
                    self.window.after(0, lambda: messagebox.showinfo(
                        "Success", 
                        f"Snapshot created successfully!\n\nName: {result.get('name', 'N/A')}\n"
                        f"Size: {result.get('size', 'N/A')} bytes",
                        parent=self.window
                    ))
                except Exception as e:
                    self.window.after(0, lambda: messagebox.showerror(
                        "Error", f"Failed to create snapshot:\n\n{str(e)}", parent=self.window
                    ))
            
            threading.Thread(target=create, daemon=True).start()
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Create", command=create_snapshot).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
    
    def _create_cluster_snapshot(self, url_config: Dict[str, Any]):
        """Open dialog to create cluster snapshot."""
        # Open the tabbed dialog instead
        dialog = SnapshotManagementDialog(self.window, url_config)
        # Switch to create tab
        dialog.window.after(100, lambda: dialog.notebook.select(0))
    
    def _recover_snapshot(self, url_config: Dict[str, Any]):
        """Open dialog to recover snapshot."""
        # Open the tabbed dialog instead
        dialog = SnapshotManagementDialog(self.window, url_config)
        # Switch to recover tab
        dialog.window.after(100, lambda: dialog.notebook.select(1))
    
    def _show_recover_dialog(self, url_config: Dict[str, Any], snapshots: List[Dict], collections: List[str]):
        """Show dialog to select snapshot to recover."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Recover Snapshot")
        dialog.geometry("600x400")
        dialog.transient(self.window)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Select Snapshot to Recover:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Listbox with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        listbox = tk.Listbox(list_frame, height=15)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate listbox
        snapshot_data = []
        for snapshot in snapshots:
            collection = snapshot.get("collection_name", "Unknown")
            name = snapshot.get("name", "Unknown")
            size = snapshot.get("size", 0)
            display = f"{collection} - {name} ({size} bytes)"
            listbox.insert(tk.END, display)
            snapshot_data.append(snapshot)
        
        if not snapshots:
            listbox.insert(tk.END, "No snapshots available")
        
        def recover_snapshot():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a snapshot.", parent=dialog)
                return
            
            snapshot = snapshot_data[selection[0]]
            collection_name = snapshot.get("collection_name")
            snapshot_name = snapshot.get("name")
            
            # Get snapshot location (URL or path)
            location_dialog = tk.Toplevel(dialog)
            location_dialog.title("Snapshot Location")
            location_dialog.geometry("500x150")
            location_dialog.transient(dialog)
            location_dialog.grab_set()
            
            loc_frame = ttk.Frame(location_dialog, padding="20")
            loc_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(loc_frame, text="Snapshot Location (URL or file path):").pack(anchor=tk.W, pady=(0, 10))
            location_var = tk.StringVar()
            ttk.Entry(loc_frame, textvariable=location_var, width=50).pack(fill=tk.X, pady=(0, 20))
            
            def do_recover():
                location = location_var.get().strip()
                if not location:
                    messagebox.showwarning("No Location", "Please enter snapshot location.", parent=location_dialog)
                    return
                
                location_dialog.destroy()
                dialog.destroy()
                
                def recover():
                    try:
                        api_key = self._get_api_key()
                        result = SnapshotService.recover_collection_snapshot(
                            url_config["url"],
                            url_config["port"],
                            url_config["https"],
                            api_key,
                            collection_name,
                            location
                        )
                        self.window.after(0, lambda: messagebox.showinfo(
                            "Success", "Snapshot recovered successfully!", parent=self.window
                        ))
                    except Exception as e:
                        self.window.after(0, lambda: messagebox.showerror(
                            "Error", f"Failed to recover snapshot:\n\n{str(e)}", parent=self.window
                        ))
                
                threading.Thread(target=recover, daemon=True).start()
            
            btn_frame = ttk.Frame(loc_frame)
            btn_frame.pack(fill=tk.X)
            ttk.Button(btn_frame, text="Recover", command=do_recover).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(btn_frame, text="Cancel", command=location_dialog.destroy).pack(side=tk.RIGHT)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Recover", command=recover_snapshot).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
    
    def _delete_snapshot(self, url_config: Dict[str, Any]):
        """Open dialog to delete snapshot."""
        # Open the tabbed dialog instead
        dialog = SnapshotManagementDialog(self.window, url_config)
        # Switch to delete tab
        dialog.window.after(100, lambda: dialog.notebook.select(2))
    
    def _show_delete_dialog(self, url_config: Dict[str, Any], snapshots: List[Dict]):
        """Show dialog to select snapshot to delete."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Delete Snapshot")
        dialog.geometry("600x400")
        dialog.transient(self.window)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Select Snapshot to Delete:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Listbox with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        listbox = tk.Listbox(list_frame, height=15, selectmode=tk.EXTENDED)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate listbox
        snapshot_data = []
        for snapshot in snapshots:
            collection = snapshot.get("collection_name", "Unknown")
            name = snapshot.get("name", "Unknown")
            size = snapshot.get("size", 0)
            display = f"{collection} - {name} ({size} bytes)"
            listbox.insert(tk.END, display)
            snapshot_data.append(snapshot)
        
        if not snapshots:
            listbox.insert(tk.END, "No snapshots available")
        
        def delete_snapshots():
            selections = listbox.curselection()
            if not selections:
                messagebox.showwarning("No Selection", "Please select snapshot(s) to delete.", parent=dialog)
                return
            
            selected_snapshots = [snapshot_data[i] for i in selections]
            
            if not messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete {len(selected_snapshots)} snapshot(s)?\n\nThis action cannot be undone.",
                parent=dialog
            ):
                return
            
            dialog.destroy()
            
            def delete():
                errors = []
                success_count = 0
                
                for snapshot in selected_snapshots:
                    try:
                        api_key = self._get_api_key()
                        SnapshotService.delete_collection_snapshot(
                            url_config["url"],
                            url_config["port"],
                            url_config["https"],
                            api_key,
                            snapshot["collection_name"],
                            snapshot["name"]
                        )
                        success_count += 1
                    except Exception as e:
                        errors.append(f"{snapshot['collection_name']}/{snapshot['name']}: {str(e)}")
                
                def show_result():
                    if errors:
                        msg = f"Deleted {success_count} snapshot(s).\n\nErrors:\n" + "\n".join(errors)
                        messagebox.showwarning("Partial Success", msg, parent=self.window)
                    else:
                        messagebox.showinfo("Success", f"Successfully deleted {success_count} snapshot(s).", parent=self.window)
                
                self.window.after(0, show_result)
            
            threading.Thread(target=delete, daemon=True).start()
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Delete", command=delete_snapshots).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)


class SnapshotManagementDialog:
    """Tabbed dialog for managing snapshots for a specific URL."""
    
    def __init__(self, parent, url_config: Dict[str, Any]):
        self.parent = parent
        self.url_config = url_config
        self.window = tk.Toplevel(parent)
        
        url_display = f"{url_config['url']}:{url_config['port']}"
        if url_config.get('https'):
            url_display = f"https://{url_display}"
        else:
            url_display = f"http://{url_display}"
        
        self.window.title(f"Snapshot Management - {url_display}")
        self.window.geometry("800x600")
        self.window.resizable(True, True)
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
    
    def _log(self, message: str, tag: str = "info"):
        """Log a message to the log viewer."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_viewer.log(f"[{timestamp}] {message}", tag)
    
    def _get_api_key(self) -> Optional[str]:
        """Get API key from configuration."""
        return ConfigService.get("QDRANT_API_KEY") or None
    
    def _setup_ui(self):
        """Setup the dialog UI with tabs."""
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        url_display = f"{self.url_config['url']}:{self.url_config['port']}"
        title_label = ttk.Label(main_frame, text=f"Snapshot Management - {url_display}", 
                               font=("Segoe UI", 12, "bold"))
        title_label.pack(pady=(0, 15))
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Tab 1: Create Snapshot
        create_tab = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(create_tab, text="Create Snapshot")
        self._setup_create_tab(create_tab)
        
        # Tab 2: Recover Snapshot
        recover_tab = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(recover_tab, text="Recover Snapshot")
        self._setup_recover_tab(recover_tab)
        
        # Tab 3: Delete Snapshot
        delete_tab = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(delete_tab, text="Delete Snapshot")
        self._setup_delete_tab(delete_tab)
        
        # Tab 4: Logs
        logs_tab = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(logs_tab, text="Logs")
        self._setup_logs_tab(logs_tab)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT)
        
        # Initial log
        self._log("Snapshot management dialog opened", "info")
        self._log(f"URL: {self.url_config['url']}:{self.url_config['port']}", "info")
        self._log(f"HTTPS: {self.url_config.get('https', False)}", "info")
    
    def _setup_create_tab(self, parent):
        """Setup the create snapshot tab."""
        # Collection snapshot section
        collection_frame = ttk.LabelFrame(parent, text="Create Collection Snapshot", padding="15")
        collection_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        ttk.Label(collection_frame, text="Select Collection:").pack(anchor=tk.W, pady=(0, 5))
        
        collection_var = tk.StringVar()
        collection_combo = ttk.Combobox(collection_frame, textvariable=collection_var, state="readonly", width=50)
        collection_combo.pack(fill=tk.X, pady=(0, 10))
        
        def load_collections():
            self._log("Loading collections...", "info")
            def load():
                try:
                    api_key = self._get_api_key()
                    collections = SnapshotService.get_collections(
                        self.url_config["url"],
                        self.url_config["port"],
                        self.url_config["https"],
                        api_key
                    )
                    self.window.after(0, lambda: collection_combo.config(values=collections))
                    if collections:
                        self.window.after(0, lambda: collection_combo.current(0))
                    self.window.after(0, lambda: self._log(f"Loaded {len(collections)} collection(s)", "success"))
                except Exception as e:
                    error_msg = str(e)
                    self.window.after(0, lambda: self._log(f"Error loading collections: {error_msg}", "error"))
                    self.window.after(0, lambda: messagebox.showerror("Error", f"Failed to load collections:\n\n{error_msg}", parent=self.window))
            
            threading.Thread(target=load, daemon=True).start()
        
        ttk.Button(collection_frame, text="Load Collections", command=load_collections).pack(anchor=tk.W, pady=(0, 10))
        
        def create_collection_snapshot():
            collection_name = collection_var.get()
            if not collection_name:
                messagebox.showwarning("No Collection", "Please select a collection.", parent=self.window)
                return
            
            self._log(f"Creating snapshot for collection: {collection_name}", "info")
            
            def create():
                try:
                    api_key = self._get_api_key()
                    self.window.after(0, lambda: self._log(f"Connecting to {self.url_config['url']}:{self.url_config['port']}...", "info"))
                    
                    result = SnapshotService.create_collection_snapshot(
                        self.url_config["url"],
                        self.url_config["port"],
                        self.url_config["https"],
                        api_key,
                        collection_name
                    )
                    
                    snapshot_name = result.get('name', 'N/A')
                    snapshot_size = result.get('size', 'N/A')
                    self.window.after(0, lambda: self._log(f"Snapshot created successfully!", "success"))
                    self.window.after(0, lambda: self._log(f"  Name: {snapshot_name}", "info"))
                    self.window.after(0, lambda: self._log(f"  Size: {snapshot_size} bytes", "info"))
                    self.window.after(0, lambda: messagebox.showinfo(
                        "Success", 
                        f"Snapshot created successfully!\n\nName: {snapshot_name}\nSize: {snapshot_size} bytes",
                        parent=self.window
                    ))
                except Exception as e:
                    error_msg = str(e)
                    self.window.after(0, lambda: self._log(f"Error creating snapshot: {error_msg}", "error"))
                    self.window.after(0, lambda: messagebox.showerror(
                        "Error", f"Failed to create snapshot:\n\n{error_msg}", parent=self.window
                    ))
            
            threading.Thread(target=create, daemon=True).start()
        
        ttk.Button(collection_frame, text="Create Collection Snapshot", command=create_collection_snapshot).pack(anchor=tk.W, pady=(10, 0))
        
        # Cluster snapshot section
        cluster_frame = ttk.LabelFrame(parent, text="Create Cluster Snapshot", padding="15")
        cluster_frame.pack(fill=tk.X, pady=(0, 0))
        
        ttk.Label(cluster_frame, text="Create a snapshot of all collections in the cluster.").pack(anchor=tk.W, pady=(0, 10))
        
        def create_cluster_snapshot():
            if not messagebox.askyesno(
                "Confirm", 
                "Create a cluster snapshot? This will snapshot all collections.\n\nContinue?",
                parent=self.window
            ):
                return
            
            self._log("Creating cluster snapshot...", "info")
            
            def create():
                try:
                    api_key = self._get_api_key()
                    self.window.after(0, lambda: self._log(f"Connecting to {self.url_config['url']}:{self.url_config['port']}...", "info"))
                    
                    result = SnapshotService.create_cluster_snapshot(
                        self.url_config["url"],
                        self.url_config["port"],
                        self.url_config["https"],
                        api_key
                    )
                    
                    if result.get("type") == "collection_snapshots":
                        snapshots = result.get("snapshots", [])
                        success_count = sum(1 for s in snapshots if "snapshot" in s)
                        error_count = sum(1 for s in snapshots if "error" in s)
                        self.window.after(0, lambda: self._log(f"Cluster snapshot completed: {success_count} succeeded, {error_count} failed", "success" if error_count == 0 else "warning"))
                        for snapshot_info in snapshots:
                            if "snapshot" in snapshot_info:
                                coll_name = snapshot_info.get("collection", "Unknown")
                                snap_name = snapshot_info["snapshot"].get("name", "N/A")
                                self.window.after(0, lambda c=coll_name, n=snap_name: self._log(f"  {c}: {n}", "info"))
                            elif "error" in snapshot_info:
                                coll_name = snapshot_info.get("collection", "Unknown")
                                error = snapshot_info["error"]
                                self.window.after(0, lambda c=coll_name, e=error: self._log(f"  {c}: ERROR - {e}", "error"))
                        msg = f"Cluster snapshot created!\n\nCollections: {success_count} succeeded, {error_count} failed"
                    else:
                        snapshot_name = result.get('name', 'N/A')
                        self.window.after(0, lambda: self._log(f"Cluster snapshot created: {snapshot_name}", "success"))
                        msg = f"Cluster snapshot created successfully!\n\nName: {snapshot_name}"
                    
                    self.window.after(0, lambda: messagebox.showinfo("Success", msg, parent=self.window))
                except Exception as e:
                    error_msg = str(e)
                    self.window.after(0, lambda: self._log(f"Error creating cluster snapshot: {error_msg}", "error"))
                    self.window.after(0, lambda: messagebox.showerror(
                        "Error", f"Failed to create cluster snapshot:\n\n{error_msg}", parent=self.window
                    ))
            
            threading.Thread(target=create, daemon=True).start()
        
        ttk.Button(cluster_frame, text="Create Cluster Snapshot", command=create_cluster_snapshot).pack(anchor=tk.W)
    
    def _setup_recover_tab(self, parent):
        """Setup the recover snapshot tab with collection and cluster options."""
        
        # Step 1: Snapshot Type Selection
        type_frame = ttk.LabelFrame(parent, text="Step 1: Select Recovery Type", padding="10")
        type_frame.pack(fill=tk.X, pady=(0, 10))
        
        snapshot_type_var = tk.StringVar(value="collection")
        ttk.Radiobutton(type_frame, text="Collection Snapshot", 
                       variable=snapshot_type_var, value="collection").pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(type_frame, text="Full (Cluster) Snapshot", 
                       variable=snapshot_type_var, value="cluster").pack(side=tk.LEFT)
        
        # Step 2: Collection Selection (only for collection snapshots)
        collection_frame = ttk.LabelFrame(parent, text="Step 2: Select Collection", padding="10")
        collection_frame.pack(fill=tk.X, pady=(0, 10))
        
        collection_row = ttk.Frame(collection_frame)
        collection_row.pack(fill=tk.X)
        
        ttk.Label(collection_row, text="Collection:").pack(side=tk.LEFT, padx=(0, 10))
        collection_var = tk.StringVar()
        collection_combo = ttk.Combobox(collection_row, textvariable=collection_var, state="readonly", width=40)
        collection_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        snapshot_data = []  # Store snapshot metadata
        
        def load_collections():
            """Load all collections from the server."""
            self._log("Loading collections...", "info")
            
            def load():
                try:
                    api_key = self._get_api_key()
                    collections = SnapshotService.get_collections(
                        self.url_config["url"],
                        self.url_config["port"],
                        self.url_config["https"],
                        api_key
                    )
                    self.window.after(0, lambda: collection_combo.config(values=collections))
                    if collections:
                        self.window.after(0, lambda: collection_combo.current(0))
                        if snapshot_type_var.get() == "collection":
                            self.window.after(100, load_snapshots)
                    self.window.after(0, lambda: self._log(f"Loaded {len(collections)} collection(s)", "success"))
                except Exception as e:
                    error_msg = str(e)
                    self.window.after(0, lambda: self._log(f"Error loading collections: {error_msg}", "error"))
            
            threading.Thread(target=load, daemon=True).start()
        
        ttk.Button(collection_row, text="Load Collections", command=load_collections).pack(side=tk.LEFT)
        
        # Step 3: Snapshot Selection with Treeview
        snapshot_frame = ttk.LabelFrame(parent, text="Step 3: Select Snapshot (click to auto-fill location)", padding="10")
        snapshot_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Treeview with columns
        columns = ("name", "size", "created", "type")
        snapshot_tree = ttk.Treeview(snapshot_frame, columns=columns, show="headings", height=8)
        
        snapshot_tree.heading("name", text="Snapshot Name")
        snapshot_tree.heading("size", text="Size")
        snapshot_tree.heading("created", text="Created")
        snapshot_tree.heading("type", text="Type")
        
        snapshot_tree.column("name", width=300, minwidth=200)
        snapshot_tree.column("size", width=100, minwidth=80)
        snapshot_tree.column("created", width=150, minwidth=100)
        snapshot_tree.column("type", width=100, minwidth=80)
        
        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(snapshot_frame, orient=tk.VERTICAL, command=snapshot_tree.yview)
        snapshot_tree.configure(yscrollcommand=tree_scroll_y.set)
        
        snapshot_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        def format_size(size_bytes):
            """Format size in human readable format."""
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
        
        def format_time(creation_time):
            """Format creation time."""
            if not creation_time:
                return "N/A"
            try:
                if "T" in str(creation_time):
                    return str(creation_time).split(".")[0].replace("T", " ")
                return str(creation_time)
            except:
                return str(creation_time)
        
        def get_download_url(collection_name: str, snapshot_name: str) -> str:
            """Generate the download URL for a collection snapshot."""
            scheme = "https" if self.url_config["https"] else "http"
            return f"{scheme}://{self.url_config['url']}:{self.url_config['port']}/collections/{collection_name}/snapshots/{snapshot_name}"
        
        def get_full_snapshot_url(snapshot_name: str) -> str:
            """Generate the download URL for a full snapshot."""
            scheme = "https" if self.url_config["https"] else "http"
            return f"{scheme}://{self.url_config['url']}:{self.url_config['port']}/snapshots/{snapshot_name}"
        
        def load_snapshots():
            """Load snapshots based on selected type."""
            # Clear existing items
            for item in snapshot_tree.get_children():
                snapshot_tree.delete(item)
            snapshot_data.clear()
            location_var.set("")
            
            snap_type = snapshot_type_var.get()
            
            if snap_type == "collection":
                collection_name = collection_var.get()
                if not collection_name:
                    self._log("Please select a collection first", "warning")
                    return
                
                self._log(f"Loading snapshots for '{collection_name}'...", "info")
                
                def load():
                    try:
                        api_key = self._get_api_key()
                        snapshots = SnapshotService.list_collection_snapshots(
                            self.url_config["url"],
                            self.url_config["port"],
                            self.url_config["https"],
                            api_key,
                            collection_name
                        )
                        
                        def update_tree():
                            for snapshot in (snapshots if isinstance(snapshots, list) else []):
                                if not isinstance(snapshot, dict):
                                    continue
                                name = snapshot.get("name", "Unknown")
                                size = snapshot.get("size", 0)
                                creation_time = snapshot.get("creation_time", "")
                                download_url = get_download_url(collection_name, name)
                                
                                item_id = snapshot_tree.insert("", tk.END, values=(
                                    name,
                                    format_size(size),
                                    format_time(creation_time),
                                    "Collection"
                                ))
                                
                                snapshot_data.append({
                                    "item_id": item_id,
                                    "type": "collection",
                                    "collection": collection_name,
                                    "snapshot": snapshot,
                                    "download_url": download_url
                                })
                            
                            self._log(f"Loaded {len(snapshot_data)} snapshot(s)", "success")
                        
                        self.window.after(0, update_tree)
                        
                    except Exception as e:
                        error_msg = str(e)
                        self.window.after(0, lambda: self._log(f"Error loading snapshots: {error_msg}", "error"))
                
                threading.Thread(target=load, daemon=True).start()
                
            else:  # cluster/full snapshots
                self._log("Loading full (cluster) snapshots...", "info")
                
                def load():
                    try:
                        api_key = self._get_api_key()
                        snapshots = SnapshotService.list_cluster_snapshots(
                            self.url_config["url"],
                            self.url_config["port"],
                            self.url_config["https"],
                            api_key
                        )
                        
                        def update_tree():
                            for snapshot in (snapshots if isinstance(snapshots, list) else []):
                                if not isinstance(snapshot, dict):
                                    continue
                                name = snapshot.get("name", "Unknown")
                                size = snapshot.get("size", 0)
                                creation_time = snapshot.get("creation_time", "")
                                download_url = get_full_snapshot_url(name)
                                
                                item_id = snapshot_tree.insert("", tk.END, values=(
                                    name,
                                    format_size(size),
                                    format_time(creation_time),
                                    "Full"
                                ))
                                
                                snapshot_data.append({
                                    "item_id": item_id,
                                    "type": "cluster",
                                    "collection": "",
                                    "snapshot": snapshot,
                                    "download_url": download_url
                                })
                            
                            self._log(f"Loaded {len(snapshot_data)} full snapshot(s)", "success")
                        
                        self.window.after(0, update_tree)
                        
                    except Exception as e:
                        error_msg = str(e)
                        self.window.after(0, lambda: self._log(f"Error loading snapshots: {error_msg}", "error"))
                
                threading.Thread(target=load, daemon=True).start()
        
        def on_type_change():
            """Handle snapshot type change."""
            if snapshot_type_var.get() == "collection":
                collection_frame.pack(fill=tk.X, pady=(0, 10), after=type_frame)
            else:
                collection_frame.pack_forget()
            # Clear tree when type changes
            for item in snapshot_tree.get_children():
                snapshot_tree.delete(item)
            snapshot_data.clear()
            location_var.set("")
        
        snapshot_type_var.trace("w", lambda *args: on_type_change())
        collection_combo.bind("<<ComboboxSelected>>", lambda e: load_snapshots() if snapshot_type_var.get() == "collection" else None)
        
        # Refresh button
        ttk.Button(snapshot_frame, text="Refresh Snapshots", command=load_snapshots).pack(anchor=tk.W, pady=(5, 0))
        
        # Step 4: Location Input
        location_frame = ttk.LabelFrame(parent, text="Step 4: Snapshot Location & Options", padding="10")
        location_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Location URL
        ttk.Label(location_frame, text="Location URL (auto-filled when you click a snapshot):", 
                 font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(0, 5))
        
        location_var = tk.StringVar()
        location_entry = ttk.Entry(location_frame, textvariable=location_var, font=("Consolas", 9))
        location_entry.pack(fill=tk.X, pady=(0, 10))
        
        # Source Server API Key (for authenticated URLs)
        auth_frame = ttk.Frame(location_frame)
        auth_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(auth_frame, text="Source Server API Key (if URL requires authentication):", 
                 font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(0, 5))
        
        source_api_key_var = tk.StringVar()
        source_api_key_entry = ttk.Entry(auth_frame, textvariable=source_api_key_var, font=("Consolas", 9), show="*")
        source_api_key_entry.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 5))
        
        # Toggle show/hide API key
        show_key_var = tk.BooleanVar(value=False)
        def toggle_show_key():
            source_api_key_entry.config(show="" if show_key_var.get() else "*")
        ttk.Checkbutton(auth_frame, text="Show", variable=show_key_var, command=toggle_show_key).pack(side=tk.LEFT)
        
        # Auto-fill source API key checkbox
        auto_fill_key_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(location_frame, text="Auto-fill source API key from current connection", 
                       variable=auto_fill_key_var).pack(anchor=tk.W, pady=(5, 5))
        
        # Pre-download option (RECOMMENDED for large snapshots)
        pre_download_var = tk.BooleanVar(value=True)  # Default to True for better performance
        pre_download_check = ttk.Checkbutton(
            location_frame, 
            text="⚡ Pre-download snapshot locally first (RECOMMENDED for snapshots >1GB - much faster!)",
            variable=pre_download_var
        )
        pre_download_check.pack(anchor=tk.W, pady=(5, 5))
        
        # Pre-download path (optional)
        pre_download_path_frame = ttk.Frame(location_frame)
        pre_download_path_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(pre_download_path_frame, text="Pre-download path (optional, leave empty for temp directory):", 
                 font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(0, 5))
        
        pre_download_path_var = tk.StringVar()
        pre_download_path_entry = ttk.Entry(pre_download_path_frame, textvariable=pre_download_path_var, font=("Consolas", 9))
        pre_download_path_entry.pack(fill=tk.X)
        
        # Show/hide pre-download path based on checkbox
        def toggle_pre_download_path(*args):
            location = location_var.get()
            if pre_download_var.get() and location and (location.startswith("http://") or location.startswith("https://")):
                pre_download_path_frame.pack(fill=tk.X, pady=(0, 5), after=pre_download_check)
            else:
                pre_download_path_frame.pack_forget()
        
        pre_download_var.trace("w", toggle_pre_download_path)
        location_var.trace("w", toggle_pre_download_path)
        # Initial state
        toggle_pre_download_path()
        
        # Recovery Priority Selection (only for collection snapshots in distributed clusters)
        priority_frame = ttk.Frame(location_frame)
        priority_frame.pack(fill=tk.X, pady=(10, 5))
        
        ttk.Label(priority_frame, text="Recovery Priority (for distributed clusters):", 
                 font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        priority_var = tk.StringVar(value="snapshot")
        
        ttk.Radiobutton(priority_frame, text="Snapshot (restore from file)", 
                       variable=priority_var, value="snapshot").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(priority_frame, text="Replica (prefer existing replicas)", 
                       variable=priority_var, value="replica").pack(side=tk.LEFT)
        
        # Info label
        info_label = ttk.Label(location_frame, 
            text="💡 For distributed clusters:\n"
                 "   • Snapshot (default): Restore from snapshot file, other nodes sync from this node\n"
                 "   • Replica: Prefer existing healthy replicas over snapshot (avoid overwriting good data)\n"
                 "⚠️ Full snapshot recovery may require server restart with --snapshot-path flag.",
            font=("Segoe UI", 8), foreground="gray", justify=tk.LEFT)
        info_label.pack(anchor=tk.W)
        
        def on_snapshot_select(event):
            """Handle snapshot selection - auto-fill the location with download URL."""
            selection = snapshot_tree.selection()
            if not selection:
                return
            
            item_id = selection[0]
            for data in snapshot_data:
                if data["item_id"] == item_id:
                    download_url = data["download_url"]
                    location_var.set(download_url)
                    self._log(f"Selected: {data['snapshot'].get('name', 'Unknown')}", "info")
                    
                    # Auto-fill source API key if option is checked
                    if auto_fill_key_var.get():
                        current_api_key = self._get_api_key()
                        if current_api_key:
                            source_api_key_var.set(current_api_key)
                    break
        
        snapshot_tree.bind("<<TreeviewSelect>>", on_snapshot_select)
        
        # Double-click to copy URL to clipboard
        def on_double_click(event):
            """Copy the download URL to clipboard on double-click."""
            selection = snapshot_tree.selection()
            if not selection:
                return
            
            item_id = selection[0]
            for data in snapshot_data:
                if data["item_id"] == item_id:
                    download_url = data["download_url"]
                    self.window.clipboard_clear()
                    self.window.clipboard_append(download_url)
                    self._log(f"Copied URL to clipboard: {download_url}", "success")
                    break
        
        snapshot_tree.bind("<Double-1>", on_double_click)
        
        # Step 5: Recover Button
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X)
        
        def recover_snapshot():
            """Execute snapshot recovery."""
            snap_type = snapshot_type_var.get()
            location = location_var.get().strip()
            
            if not location:
                messagebox.showwarning("No Location", "Please enter the snapshot location.", parent=self.window)
                return
            
            # Get selected snapshot name for logging
            selection = snapshot_tree.selection()
            snapshot_name = "unknown"
            selected_data = None
            if selection:
                for data in snapshot_data:
                    if data["item_id"] == selection[0]:
                        snapshot_name = data["snapshot"].get("name", "unknown")
                        selected_data = data
                        break
            
            priority = priority_var.get()
            source_api_key = source_api_key_var.get().strip() or None
            pre_download = pre_download_var.get()
            pre_download_path = pre_download_path_var.get().strip() or None
            
            if snap_type == "collection":
                collection_name = collection_var.get()
                if not collection_name:
                    messagebox.showwarning("No Collection", "Please select a collection first.", parent=self.window)
                    return
                
                # Confirm recovery
                if priority == "snapshot":
                    priority_desc = "Restore from snapshot file (other cluster nodes will sync from this)"
                else:
                    priority_desc = "Prefer existing healthy replicas over snapshot"
                
                # Build confirmation message
                confirm_msg = f"Recover collection '{collection_name}' from snapshot?\n\n"
                confirm_msg += f"Snapshot: {snapshot_name}\n"
                confirm_msg += f"Location: {location}\n\n"
                confirm_msg += f"Priority: {priority.upper()}\n"
                confirm_msg += f"→ {priority_desc}\n\n"
                
                if pre_download and (location.startswith("http://") or location.startswith("https://")):
                    confirm_msg += f"⚡ Pre-download: ENABLED (faster recovery)\n"
                    if pre_download_path:
                        confirm_msg += f"   Path: {pre_download_path}\n"
                    else:
                        confirm_msg += f"   Path: Temp directory\n"
                    confirm_msg += "\n"
                
                confirm_msg += f"⚠️ This will restore the collection from the snapshot."
                
                confirm = messagebox.askyesno(
                    "Confirm Recovery",
                    confirm_msg,
                    parent=self.window
                )
                if not confirm:
                    return
                
                self._log(f"Recovering collection '{collection_name}'...", "info")
                self._log(f"Snapshot: {snapshot_name}", "info")
                self._log(f"Location: {location}", "info")
                self._log(f"Priority: {priority}", "info")
                if pre_download:
                    self._log(f"Pre-download: ENABLED (faster recovery)", "info")
                
                def recover():
                    try:
                        api_key = self._get_api_key()
                        self.window.after(0, lambda: self._log("Connecting to Qdrant server...", "info"))
                        
                        SnapshotService.recover_collection_snapshot(
                            self.url_config["url"],
                            self.url_config["port"],
                            self.url_config["https"],
                            api_key,
                            collection_name,
                            location,
                            priority=priority,
                            location_api_key=source_api_key,
                            pre_download=pre_download,
                            pre_download_path=pre_download_path
                        )
                        
                        self.window.after(0, lambda: self._log("✅ Collection recovered successfully!", "success"))
                        self.window.after(0, lambda: messagebox.showinfo(
                            "Success", 
                            f"Collection '{collection_name}' recovered successfully!",
                            parent=self.window
                        ))
                    except Exception as e:
                        error_msg = str(e)
                        self.window.after(0, lambda: self._log(f"❌ Recovery failed: {error_msg}", "error"))
                        self.window.after(0, lambda: messagebox.showerror(
                            "Recovery Failed",
                            f"Failed to recover collection:\n\n{error_msg}",
                            parent=self.window
                        ))
                
                threading.Thread(target=recover, daemon=True).start()
                
            else:  # cluster/full snapshot recovery
                confirm = messagebox.askyesno(
                    "Confirm Full Snapshot Recovery",
                    f"Recover from full (cluster) snapshot?\n\n"
                    f"Snapshot: {snapshot_name}\n"
                    f"Location: {location}\n\n"
                    f"⚠️ WARNING: Full snapshot recovery via API may not be supported.\n"
                    f"You may need to restart the server with:\n"
                    f"  --snapshot-path {location}\n\n"
                    f"Attempt API recovery anyway?",
                    parent=self.window
                )
                if not confirm:
                    return
                
                self._log(f"Attempting full snapshot recovery...", "info")
                self._log(f"Snapshot: {snapshot_name}", "info")
                self._log(f"Location: {location}", "info")
                
                def recover():
                    try:
                        api_key = self._get_api_key()
                        self.window.after(0, lambda: self._log("Connecting to Qdrant server...", "info"))
                        
                        SnapshotService.recover_cluster_snapshot(
                            self.url_config["url"],
                            self.url_config["port"],
                            self.url_config["https"],
                            api_key,
                            location,
                            priority=priority
                        )
                        
                        self.window.after(0, lambda: self._log("✅ Full snapshot recovery initiated!", "success"))
                        self.window.after(0, lambda: messagebox.showinfo(
                            "Success", 
                            "Full snapshot recovery initiated!\n\n"
                            "Note: You may need to restart the server for changes to take effect.",
                            parent=self.window
                        ))
                    except Exception as e:
                        error_msg = str(e)
                        self.window.after(0, lambda: self._log(f"❌ Recovery failed: {error_msg}", "error"))
                        self.window.after(0, lambda: messagebox.showerror(
                            "Recovery Failed",
                            f"Full snapshot recovery via API failed.\n\n"
                            f"Error: {error_msg}\n\n"
                            f"Try restarting the server with:\n"
                            f"  --snapshot-path <path-to-snapshot>",
                            parent=self.window
                        ))
                
                threading.Thread(target=recover, daemon=True).start()
        
        ttk.Button(button_frame, text="🔄 Recover Snapshot", command=recover_snapshot).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Load Collections", command=load_collections).pack(side=tk.LEFT)
    
    def _setup_delete_tab(self, parent):
        """Setup the delete snapshot tab with table view."""
        
        # Step 1: Snapshot Type Selection
        type_frame = ttk.LabelFrame(parent, text="Step 1: Select Snapshot Type", padding="10")
        type_frame.pack(fill=tk.X, pady=(0, 10))
        
        snapshot_type_var = tk.StringVar(value="collection")
        ttk.Radiobutton(type_frame, text="Collection Snapshots", 
                       variable=snapshot_type_var, value="collection").pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(type_frame, text="Full (Cluster) Snapshots", 
                       variable=snapshot_type_var, value="cluster").pack(side=tk.LEFT)
        
        # Step 2: Collection Selection (only for collection snapshots)
        collection_frame = ttk.LabelFrame(parent, text="Step 2: Select Collection", padding="10")
        collection_frame.pack(fill=tk.X, pady=(0, 10))
        
        collection_row = ttk.Frame(collection_frame)
        collection_row.pack(fill=tk.X)
        
        ttk.Label(collection_row, text="Collection:").pack(side=tk.LEFT, padx=(0, 10))
        collection_var = tk.StringVar()
        collection_combo = ttk.Combobox(collection_row, textvariable=collection_var, state="readonly", width=40)
        collection_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        snapshot_data = []  # Store snapshot metadata
        
        def load_collections():
            """Load all collections from the server."""
            self._log("Loading collections...", "info")
            
            def load():
                try:
                    api_key = self._get_api_key()
                    collections = SnapshotService.get_collections(
                        self.url_config["url"],
                        self.url_config["port"],
                        self.url_config["https"],
                        api_key
                    )
                    self.window.after(0, lambda: collection_combo.config(values=collections))
                    if collections:
                        self.window.after(0, lambda: collection_combo.current(0))
                        self.window.after(100, load_snapshots)
                    self.window.after(0, lambda: self._log(f"Loaded {len(collections)} collection(s)", "success"))
                except Exception as e:
                    error_msg = str(e)
                    self.window.after(0, lambda: self._log(f"Error loading collections: {error_msg}", "error"))
            
            threading.Thread(target=load, daemon=True).start()
        
        ttk.Button(collection_row, text="Load Collections", command=load_collections).pack(side=tk.LEFT)
        
        # Step 3: Snapshot Table
        snapshot_frame = ttk.LabelFrame(parent, text="Step 3: Select Snapshots to Delete (Ctrl+Click for multiple)", padding="10")
        snapshot_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Treeview with columns
        columns = ("name", "size", "created", "type")
        snapshot_tree = ttk.Treeview(snapshot_frame, columns=columns, show="headings", height=10, selectmode="extended")
        
        snapshot_tree.heading("name", text="Snapshot Name")
        snapshot_tree.heading("size", text="Size")
        snapshot_tree.heading("created", text="Created")
        snapshot_tree.heading("type", text="Type")
        
        snapshot_tree.column("name", width=300, minwidth=200)
        snapshot_tree.column("size", width=100, minwidth=80)
        snapshot_tree.column("created", width=150, minwidth=100)
        snapshot_tree.column("type", width=100, minwidth=80)
        
        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(snapshot_frame, orient=tk.VERTICAL, command=snapshot_tree.yview)
        snapshot_tree.configure(yscrollcommand=tree_scroll_y.set)
        
        snapshot_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        def format_size(size_bytes):
            """Format size in human readable format."""
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
        
        def format_time(creation_time):
            """Format creation time."""
            if not creation_time:
                return "N/A"
            try:
                if "T" in str(creation_time):
                    return str(creation_time).split(".")[0].replace("T", " ")
                return str(creation_time)
            except:
                return str(creation_time)
        
        def load_snapshots():
            """Load snapshots based on selected type."""
            # Clear existing items
            for item in snapshot_tree.get_children():
                snapshot_tree.delete(item)
            snapshot_data.clear()
            
            snapshot_type = snapshot_type_var.get()
            
            if snapshot_type == "collection":
                collection_name = collection_var.get()
                if not collection_name:
                    self._log("Please select a collection first", "warning")
                    return
                
                self._log(f"Loading snapshots for '{collection_name}'...", "info")
                
                def load():
                    try:
                        api_key = self._get_api_key()
                        snapshots = SnapshotService.list_collection_snapshots(
                            self.url_config["url"],
                            self.url_config["port"],
                            self.url_config["https"],
                            api_key,
                            collection_name
                        )
                        
                        def update_tree():
                            for snapshot in (snapshots if isinstance(snapshots, list) else []):
                                if not isinstance(snapshot, dict):
                                    continue
                                
                                name = snapshot.get("name", "Unknown")
                                size = snapshot.get("size", 0)
                                creation_time = snapshot.get("creation_time", "")
                                
                                item_id = snapshot_tree.insert("", tk.END, values=(
                                    name,
                                    format_size(size),
                                    format_time(creation_time),
                                    "Collection"
                                ))
                                
                                snapshot_data.append({
                                    "item_id": item_id,
                                    "type": "collection",
                                    "collection": collection_name,
                                    "snapshot": snapshot
                                })
                            
                            self._log(f"Loaded {len(snapshot_data)} snapshot(s)", "success")
                        
                        self.window.after(0, update_tree)
                        
                    except Exception as e:
                        error_msg = str(e)
                        self.window.after(0, lambda: self._log(f"Error loading snapshots: {error_msg}", "error"))
                
                threading.Thread(target=load, daemon=True).start()
                
            else:  # cluster
                self._log("Loading full (cluster) snapshots...", "info")
                
                def load():
                    try:
                        api_key = self._get_api_key()
                        snapshots = SnapshotService.list_cluster_snapshots(
                            self.url_config["url"],
                            self.url_config["port"],
                            self.url_config["https"],
                            api_key
                        )
                        
                        def update_tree():
                            for snapshot in (snapshots if isinstance(snapshots, list) else []):
                                if not isinstance(snapshot, dict):
                                    continue
                                
                                name = snapshot.get("name", "Unknown")
                                size = snapshot.get("size", 0)
                                creation_time = snapshot.get("creation_time", "")
                                snap_type = snapshot.get("type", "full")
                                
                                item_id = snapshot_tree.insert("", tk.END, values=(
                                    name,
                                    format_size(size),
                                    format_time(creation_time),
                                    "Full" if snap_type == "full" else "Collection"
                                ))
                                
                                snapshot_data.append({
                                    "item_id": item_id,
                                    "type": "cluster",
                                    "collection": "",
                                    "snapshot": snapshot
                                })
                            
                            self._log(f"Loaded {len(snapshot_data)} full snapshot(s)", "success")
                        
                        self.window.after(0, update_tree)
                        
                    except Exception as e:
                        error_msg = str(e)
                        self.window.after(0, lambda: self._log(f"Error loading snapshots: {error_msg}", "error"))
                
                threading.Thread(target=load, daemon=True).start()
        
        def on_type_change():
            """Handle snapshot type change."""
            if snapshot_type_var.get() == "collection":
                collection_frame.pack(fill=tk.X, pady=(0, 10), after=type_frame)
            else:
                collection_frame.pack_forget()
            # Clear tree when type changes
            for item in snapshot_tree.get_children():
                snapshot_tree.delete(item)
            snapshot_data.clear()
        
        snapshot_type_var.trace("w", lambda *args: on_type_change())
        collection_combo.bind("<<ComboboxSelected>>", lambda e: load_snapshots())
        
        # Refresh button under table
        ttk.Button(snapshot_frame, text="Refresh Snapshots", command=load_snapshots).pack(anchor=tk.W, pady=(5, 0))
        
        # Step 4: Delete Button
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X)
        
        def get_selected_count():
            """Get count of selected items."""
            return len(snapshot_tree.selection())
        
        def delete_snapshots():
            """Delete selected snapshots."""
            selections = snapshot_tree.selection()
            if not selections:
                messagebox.showwarning("No Selection", "Please select snapshot(s) to delete.", parent=self.window)
                return
            
            # Find selected snapshot data
            selected_snapshots = []
            for item_id in selections:
                for data in snapshot_data:
                    if data["item_id"] == item_id:
                        selected_snapshots.append(data)
                        break
            
            if not selected_snapshots:
                return
            
            snapshot_names = [s["snapshot"].get("name", "Unknown") for s in selected_snapshots]
            
            # Confirm deletion
            if not messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete {len(selected_snapshots)} snapshot(s)?\n\n"
                f"Snapshots:\n" + "\n".join(f"  • {n}" for n in snapshot_names[:5]) +
                (f"\n  ... and {len(snapshot_names) - 5} more" if len(snapshot_names) > 5 else "") +
                f"\n\n⚠️ This action cannot be undone!",
                parent=self.window
            ):
                return
            
            self._log(f"Deleting {len(selected_snapshots)} snapshot(s)...", "info")
            
            def delete():
                errors = []
                success_count = 0
                
                for snapshot_info in selected_snapshots:
                    snapshot = snapshot_info["snapshot"]
                    snapshot_name = snapshot.get("name", "Unknown")
                    snapshot_type_info = snapshot_info["type"]
                    
                    try:
                        api_key = self._get_api_key()
                        self.window.after(0, lambda n=snapshot_name: self._log(f"Deleting: {n}...", "info"))
                        
                        if snapshot_type_info == "collection":
                            collection_name = snapshot_info["collection"]
                            SnapshotService.delete_collection_snapshot(
                                self.url_config["url"],
                                self.url_config["port"],
                                self.url_config["https"],
                                api_key,
                                collection_name,
                                snapshot_name
                            )
                        else:  # cluster/full
                            SnapshotService.delete_cluster_snapshot(
                                self.url_config["url"],
                                self.url_config["port"],
                                self.url_config["https"],
                                api_key,
                                snapshot_name
                            )
                        
                        success_count += 1
                        self.window.after(0, lambda n=snapshot_name: self._log(f"✅ Deleted: {n}", "success"))
                    except Exception as e:
                        error_msg = str(e)
                        errors.append(f"{snapshot_name}: {error_msg}")
                        self.window.after(0, lambda n=snapshot_name, e=error_msg: self._log(f"❌ Error deleting {n}: {e}", "error"))
                
                def show_result():
                    if errors:
                        msg = f"Deleted {success_count} snapshot(s).\n\nErrors:\n" + "\n".join(errors[:5])
                        if len(errors) > 5:
                            msg += f"\n... and {len(errors) - 5} more errors"
                        self._log(f"Deletion completed with {len(errors)} error(s)", "warning")
                        messagebox.showwarning("Partial Success", msg, parent=self.window)
                    else:
                        self._log(f"✅ Successfully deleted {success_count} snapshot(s)", "success")
                        messagebox.showinfo("Success", f"Successfully deleted {success_count} snapshot(s).", parent=self.window)
                    
                    # Reload snapshots
                    load_snapshots()
                
                self.window.after(0, show_result)
            
            threading.Thread(target=delete, daemon=True).start()
        
        ttk.Button(button_frame, text="🗑️ Delete Selected Snapshots", command=delete_snapshots).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Load Collections", command=load_collections).pack(side=tk.LEFT)
    
    def _setup_logs_tab(self, parent):
        """Setup the logs tab."""
        self.log_viewer = LogViewer(parent)
        self.log_viewer.pack(fill=tk.BOTH, expand=True)

