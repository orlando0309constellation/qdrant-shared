"""
Operation Controller - Handles execution of shard operations.
"""

import sys
import threading
from io import StringIO
from typing import Optional, Dict, List
from tkinter import messagebox

from qdrant_distributed.models.shard import ShardInfo
from qdrant_distributed.models import PeerInfo
from qdrant_distributed.exceptions import QdrantShardingError, ValidationError
from qdrant_distributed.client import ClusterClient

from qdrant_distributed.interface.services.app_state import AppState
from qdrant_distributed.interface.controllers.service_controller import ServiceController
from qdrant_distributed.interface.controllers.validation_controller import ValidationController


class OperationController:
    """Handles execution of shard operations."""
    
    def __init__(self, app_state: AppState, service_controller: ServiceController, 
                 validation_controller: ValidationController):
        self.app_state = app_state
        self.service_controller = service_controller
        self.validation_controller = validation_controller
        self._callbacks = {}
    
    def register_callback(self, event: str, callback):
        """Register a callback for operation events."""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)
    
    def _emit(self, event: str, *args, **kwargs):
        """Emit an event to registered callbacks."""
        for callback in self._callbacks.get(event, []):
            callback(*args, **kwargs)
    
    def _call_with_return(self, event: str, *args, **kwargs):
        """Call callbacks and return the first non-None result."""
        for callback in self._callbacks.get(event, []):
            result = callback(*args, **kwargs)
            if result is not None:
                return result
        return None
    
    def execute_operation(self):
        """Execute the selected operation in a separate thread."""
        # Validate inputs first
        is_valid, error_msg = self.validation_controller.validate_inputs()
        if not is_valid:
            messagebox.showerror("Validation Error", error_msg)
            return
        
        self._emit("operation_start")
        thread = threading.Thread(target=self._execute_operation_thread, daemon=True)
        thread.start()
    
    def _execute_operation_thread(self):
        """Execute operation in background thread."""
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        try:
            operation = self.app_state.operation_var.get()
            collection = self.app_state.collection_var.get()
            timeout = int(self.app_state.timeout_var.get())
            
            self._emit("progress_update", 10, "Initializing services...")
            self.service_controller.initialize_qdrant()
            self._emit("progress_update", 20, "Services initialized")
            
            if operation == "list":
                self._execute_list_operation(collection, timeout)
            elif operation == "move":
                self._execute_move_operation(collection, timeout)
            elif operation == "replicate":
                self._execute_replicate_operation(collection, timeout)
            elif operation == "abort":
                self._execute_abort_operation(collection, timeout)
            
            self._emit("progress_update", 90, "Finalizing...")
            
            # Get captured output
            output = sys.stdout.getvalue()
            if output:
                self._emit("log_output", output)
            
            sys.stdout = old_stdout
            self._emit("progress_update", 100)
            self._emit("log_output", "\n" + "=" * 80, "header")
            self._emit("log_output", "✨ Operation completed successfully", "success")
            self._emit("log_output", "=" * 80, "header")
            self._emit("status_update", "Operation completed successfully")
            
        except Exception as e:
            sys.stdout = old_stdout
            self._emit("log_output", f"\n❌ Error: {type(e).__name__}: {str(e)}", "error")
            self._emit("status_update", f"Error: {str(e)}")
            self._emit("error", str(e))
        finally:
            self._emit("operation_complete")
    
    def _execute_list_operation(self, collection: str, timeout: int):
        """Execute list shards operation."""
        self._emit("log_output", "📋 Listing all local shards from each peer in the cluster\n", "info")
        self._emit("progress_update", 30, "Fetching shard information...")
        
        if self.app_state.last_mongo_var.get():
            self.service_controller.ensure_mysql_initialized()
            mysql_service = self.service_controller.get_mysql_service()
            if mysql_service is None:
                raise ValueError("MySQL service not initialized. Please check MySQL connection settings.")
            self._emit("progress_update", 50, "Loading from MySQL...")
            latest_doc = mysql_service.get_latest_peers()
            peer_shards = mysql_service.get_latest_peers_as_dict(latest_doc)
            peer_uris = mysql_service.get_latest_peer_uris(latest_doc)
            self._emit("progress_update", 80, "Processing data...")
            self._emit("display_shards", peer_shards, peer_uris)
        else:
            self._emit("progress_update", 40, "Connecting to cluster...")
            cluster_ops = self.service_controller.get_cluster_ops()
            peer_shards = cluster_ops.list_all_shards(collection_name=collection, timeout=timeout)
            self._emit("progress_update", 60, "Retrieving peer information...")
            
            cluster_client = ClusterClient()
            peers_dict, _ = cluster_client.get_peers(timeout)
            peer_uris = {int(pid): peer_data.get("uri", "") for pid, peer_data in peers_dict.items()}
            self._emit("progress_update", 70, "Processing results...")
            
            self._emit("display_shards", peer_shards, peer_uris)
            
            # Save to MySQL if requested
            if self.app_state.save_var.get():
                self.service_controller.ensure_mysql_initialized()
                mysql_service = self.service_controller.get_mysql_service()
                if mysql_service is None:
                    raise ValueError("MySQL service not initialized. Please check MySQL connection settings.")
                self._emit("log_output", "\n💾 Saving peer information to MySQL...", "info")
                self._emit("progress_update", 85, "Saving to MySQL...")
                peer_info_list = self._convert_peer_shards_to_peer_info(peer_shards, peers_dict)
                mysql_service.save_peers(peer_info_list)
                self._emit("log_output", "✓ Peer information saved to MySQL", "success")
    
    def _execute_move_operation(self, collection: str, timeout: int):
        """Execute move shards operation."""
        from_peer = int(self.app_state.from_peer_var.get())
        to_peer = int(self.app_state.to_peer_var.get())
        method = self.app_state.method_var.get()
        
        # Get selected shard IDs (will be handled by view)
        selected_shard_ids = self._call_with_return("get_selected_shards", from_peer) or []
        
        if selected_shard_ids:
            self._emit("log_output", f"🚀 Moving shards {selected_shard_ids} from peer {from_peer} to peer {to_peer}", "info")
        else:
            self._emit("log_output", f"🚀 Moving all shards from peer {from_peer} to peer {to_peer}", "info")
        self._emit("log_output", f"   Method: {method}\n", "info")
        self._emit("progress_update", 30)
        
        # Get shard information
        if self.app_state.latest_var.get():
            self.service_controller.ensure_mysql_initialized()
            mysql_service = self.service_controller.get_mysql_service()
            if mysql_service is None:
                raise ValueError("MySQL service not initialized. Please check MySQL connection settings.")
            self._emit("log_output", "📋 Getting shard information from MySQL (latest)...", "info")
            all_peer_shards = mysql_service.get_latest_peers_as_dict()
            self._emit("log_output", "✓ Retrieved peer information from MySQL\n", "success")
            self._emit("progress_update", 50)
        else:
            self._emit("log_output", "📋 Getting shard information from peers...", "info")
            cluster_ops = self.service_controller.get_cluster_ops()
            all_peer_shards = cluster_ops.list_all_shards(collection_name=collection, timeout=timeout)
            self._emit("log_output", "")
            self._emit("progress_update", 50)
        
        # Validate replicate factor
        if not selected_shard_ids:
            from_peer_shards = all_peer_shards.get(from_peer, [])
            selected_shard_ids = [shard.shard_id for shard in from_peer_shards]
        
        is_valid, error_msg = self.validation_controller.validate_replicate_factor(
            all_peer_shards, selected_shard_ids, from_peer, to_peer, "move"
        )
        if not is_valid:
            raise ValidationError(error_msg)
        
        # Execute move
        self._emit("progress_update", 60, "Executing move operation...")
        shard_ops = self.service_controller.get_shard_ops()
        method_enum = self._get_method_enum(method)
        
        if selected_shard_ids:
            total = len(selected_shard_ids)
            for idx, shard_id in enumerate(selected_shard_ids):
                self._emit("progress_update", 60 + int((idx / total) * 20), 
                          f"Moving shard {shard_id} ({idx+1}/{total})...")
                shard_ops.move_shard(
                    collection_name=collection,
                    shard_id=shard_id,
                    from_peer_id=from_peer,
                    to_peer_id=to_peer,
                    method=method_enum,
                    timeout=timeout
                )
        else:
            self._emit("progress_update", 70, "Moving all shards...")
            shard_ops.move_shard(
                collection_name=collection,
                shard_id=None,
                from_peer_id=from_peer,
                to_peer_id=to_peer,
                method=method_enum,
                timeout=timeout
            )
        
        self._emit("progress_update", 85, "Move operation completed")
        self._emit("log_output", "✓ Move operation completed\n", "success")
    
    def _execute_replicate_operation(self, collection: str, timeout: int):
        """Execute replicate shards operation."""
        from_peer = int(self.app_state.from_peer_var.get())
        to_peer = int(self.app_state.to_peer_var.get())
        method = self.app_state.method_var.get()
        
        selected_shard_ids = []
        for callback in self._callbacks.get("get_selected_shards", []):
            result = callback(from_peer)
            if result:
                selected_shard_ids = result
                break
        
        if selected_shard_ids:
            self._emit("log_output", f"🔄 Replicating shards {selected_shard_ids} from peer {from_peer} to peer {to_peer}", "info")
        else:
            self._emit("log_output", f"🔄 Replicating all shards from peer {from_peer} to peer {to_peer}", "info")
        self._emit("log_output", f"   Method: {method}\n", "info")
        self._emit("progress_update", 30, "Preparing operation...")
        
        # Get shard information
        if self.app_state.latest_var.get():
            self.service_controller.ensure_mysql_initialized()
            mysql_service = self.service_controller.get_mysql_service()
            if mysql_service is None:
                raise ValueError("MySQL service not initialized. Please check MySQL connection settings.")
            self._emit("log_output", "📋 Getting shard information from MySQL (latest)...", "info")
            self._emit("progress_update", 40, "Loading from MySQL...")
            all_peer_shards = mysql_service.get_latest_peers_as_dict()
            self._emit("log_output", "✓ Retrieved peer information from MySQL\n", "success")
            self._emit("progress_update", 50, "Validating shards...")
        else:
            self._emit("log_output", "📋 Getting shard information from peers...", "info")
            self._emit("progress_update", 40, "Connecting to cluster...")
            cluster_ops = self.service_controller.get_cluster_ops()
            all_peer_shards = cluster_ops.list_all_shards(collection_name=collection, timeout=timeout)
            self._emit("log_output", "")
            self._emit("progress_update", 50, "Validating shards...")
        
        # Validate replicate factor
        if not selected_shard_ids:
            from_peer_shards = all_peer_shards.get(from_peer, [])
            selected_shard_ids = [shard.shard_id for shard in from_peer_shards]
        
        is_valid, error_msg = self.validation_controller.validate_replicate_factor(
            all_peer_shards, selected_shard_ids, from_peer, to_peer, "replicate"
        )
        if not is_valid:
            raise ValidationError(error_msg)
        
        # Execute replicate
        self._emit("progress_update", 60, "Executing replicate operation...")
        shard_ops = self.service_controller.get_shard_ops()
        method_enum = self._get_method_enum(method)
        
        if selected_shard_ids:
            total = len(selected_shard_ids)
            for idx, shard_id in enumerate(selected_shard_ids):
                self._emit("progress_update", 60 + int((idx / total) * 20), 
                          f"Replicating shard {shard_id} ({idx+1}/{total})...")
                shard_ops.replicate_shard(
                    collection_name=collection,
                    shard_id=shard_id,
                    from_peer_id=from_peer,
                    to_peer_id=to_peer,
                    method=method_enum,
                    timeout=timeout
                )
        else:
            self._emit("progress_update", 70, "Replicating all shards...")
            shard_ops.replicate_shard(
                collection_name=collection,
                shard_id=None,
                from_peer_id=from_peer,
                to_peer_id=to_peer,
                method=method_enum,
                timeout=timeout
            )
        
        self._emit("progress_update", 85, "Replicate operation completed")
        self._emit("log_output", "✓ Replicate operation completed\n", "success")
    
    def _execute_abort_operation(self, collection: str, timeout: int):
        """Execute abort transfer operation."""
        from_peer = int(self.app_state.from_peer_var.get())
        to_peer = int(self.app_state.to_peer_var.get())
        shard_id = int(self.app_state.shard_id_var.get())
        
        self._emit("log_output", f"🛑 Aborting transfer of shard {shard_id} from peer {from_peer} to peer {to_peer}\n", "info")
        self._emit("progress_update", 30, "Aborting transfer...")
        
        shard_ops = self.service_controller.get_shard_ops()
        shard_ops.abort_transfer(
            collection_name=collection,
            shard_id=shard_id,
            from_peer_id=from_peer,
            to_peer_id=to_peer,
            timeout=timeout
        )
        
        self._emit("progress_update", 80, "Abort operation completed")
        self._emit("log_output", "✓ Abort operation completed\n", "success")
    
    def _get_method_enum(self, method: str):
        """Convert method string to enum."""
        from qdrant_distributed.models import ShardTransferMethod
        method_map = {
            "stream_records": ShardTransferMethod.STREAM_RECORDS,
            "snapshot": ShardTransferMethod.SNAPSHOT,
        }
        return method_map.get(method, ShardTransferMethod.STREAM_RECORDS)
    
    def _convert_peer_shards_to_peer_info(self, peer_shards: Dict[int, List[ShardInfo]], 
                                          peers_dict: Dict) -> List[PeerInfo]:
        """Convert peer_shards dictionary to list of PeerInfo objects."""
        peer_info_list = []
        for peer_id, shards in peer_shards.items():
            peer_data = peers_dict.get(str(peer_id), {})
            peer_info = PeerInfo(
                peer_id=peer_id,
                uri=peer_data.get("uri", ""),
                shards=[shard.shard_id for shard in shards]
            )
            peer_info_list.append(peer_info)
        return peer_info_list

