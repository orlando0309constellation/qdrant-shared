from typing import List, Dict, Optional
from qdrant_distributed.config import MySQLManager
from qdrant_distributed.models.peer import PeerInfo
from qdrant_distributed.models.shard import ShardInfo
from datetime import datetime
import json


class MySQLService:
    def __init__(self, mysql_manager: MySQLManager = None):
        # MySQLManager uses class variables, so we just need the class reference
        # The connection is stored at MySQLManager.connection (class level)
        pass
    
    def save_peers(self, peers: List[PeerInfo]):
        """
        Save peers to MySQL with shards stored as JSON for better performance.
        
        Args:
            peers: List of PeerInfo objects to save
        """
        try:
            if MySQLManager.connection is None:
                raise ValueError("MySQL Connection not available. Please initialize MySQL first using MySQLManager.initialize()")
            
            cursor = MySQLManager.connection.cursor()
            
            try:
                # Generate snapshot ID (unix timestamp in milliseconds)
                timestamp = datetime.now()
                snapshot_id = int(timestamp.timestamp() * 1000)
                
                # Insert peers with shards as JSON (much faster - one INSERT per peer instead of N+1)
                for peer in peers:
                    # Serialize shards to JSON array
                    shards_json = json.dumps([shard.to_dict() for shard in peer.local_shards])
                    
                    # Insert peer with shards as JSON
                    cursor.execute(
                        """INSERT INTO peers (snapshot_id, peer_id, uri, shards_json, created_at) 
                           VALUES (%s, %s, %s, %s, %s)""",
                        (snapshot_id, peer.peer_id, peer.uri, shards_json, timestamp)
                    )
                
                MySQLManager.connection.commit()
            except Exception as e:
                MySQLManager.connection.rollback()
                raise e
            finally:
                cursor.close()
        except Exception as e:
            print(f"Error saving peers: {e}")
            raise e

    def get_latest_peers(self) -> Optional[Dict]:
        """
        Get the latest peers document from MySQL.
        Uses JSON column for shards - much faster (single query instead of N+1).
        
        Returns:
            Dictionary containing timestamp and peers list, or None if not found
        """
        if MySQLManager.connection is None:
            raise ValueError("MySQL Connection not available. Please initialize MySQL first using MySQLManager.initialize()")
        
        # Use dictionary=True for dictionary results (works with both C and pure Python implementation)
        cursor = MySQLManager.connection.cursor(dictionary=True)
        
        try:
            # Get latest snapshot with all peer data including JSON shards (single query!)
            cursor.execute("""
                SELECT 
                    snapshot_id,
                    peer_id,
                    uri,
                    shards_json,
                    created_at as timestamp
                FROM peers
                WHERE snapshot_id = (SELECT MAX(snapshot_id) FROM peers)
                ORDER BY peer_id
            """)
            peers_data = cursor.fetchall()
            
            if not peers_data:
                return None
            
            # Get timestamp from first row
            timestamp = peers_data[0]['timestamp']
            snapshot_id = peers_data[0]['snapshot_id']
            
            # Parse peers with shards from JSON
            peers_list = []
            for peer_data in peers_data:
                peer_id = peer_data['peer_id']
                
                # Parse shards from JSON column
                shards_json = peer_data.get('shards_json')
                if shards_json:
                    if isinstance(shards_json, str):
                        shards_data = json.loads(shards_json)
                    else:
                        # MySQL JSON column may return dict/list directly
                        shards_data = shards_json if isinstance(shards_json, list) else json.loads(str(shards_json))
                else:
                    shards_data = []
                
                # Convert to ShardInfo objects
                shards = [ShardInfo.from_dict(shard) for shard in shards_data]
                
                peer_dict = {
                    "peer_id": peer_id,
                    "uri": peer_data.get('uri') or "",
                    "local_shards": [shard.to_dict() for shard in shards]
                }
                peers_list.append(peer_dict)
            
            return {
                "timestamp": timestamp,
                "peers": peers_list
            }
        finally:
            cursor.close()
    
    def get_latest_peers_as_dict(self, latest_doc: Dict = None) -> Dict[int, List[ShardInfo]]:
        """
        Get the latest peers from MySQL and convert to the format used by list_all_shards.
        
        Args:
            latest_doc: Optional pre-fetched document to avoid duplicate queries
        
        Returns:
            Dictionary mapping peer_id to list of ShardInfo objects
        
        Raises:
            ValueError: If no peer data found in MySQL
        """
        if latest_doc is None:
            latest_doc = self.get_latest_peers()
        if latest_doc is None or "peers" not in latest_doc:
            raise ValueError("No peer data found in MySQL")
        
        # Convert MySQL data to Dict[int, List[ShardInfo]]
        peer_shards: Dict[int, List[ShardInfo]] = {}
        for peer_data in latest_doc["peers"]:
            peer_id = peer_data["peer_id"]
            shards = [ShardInfo.from_dict(shard_dict) for shard_dict in peer_data.get("local_shards", [])]
            peer_shards[peer_id] = shards
        
        return peer_shards
    
    def get_latest_peer_uris(self, latest_doc: Dict = None) -> Dict[int, str]:
        """
        Get the latest peer URIs from MySQL.
        
        Args:
            latest_doc: Optional pre-fetched document to avoid duplicate queries
        
        Returns:
            Dictionary mapping peer_id to URI string
        
        Raises:
            ValueError: If no peer data found in MySQL
        """
        if latest_doc is None:
            latest_doc = self.get_latest_peers()
        if latest_doc is None or "peers" not in latest_doc:
            raise ValueError("No peer data found in MySQL")
        
        # Extract URIs from MySQL data
        peer_uris: Dict[int, str] = {}
        for peer_data in latest_doc["peers"]:
            peer_id = peer_data["peer_id"]
            uri = peer_data.get("uri", "")
            peer_uris[peer_id] = uri
        
        return peer_uris

