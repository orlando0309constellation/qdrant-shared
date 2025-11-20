from typing import List, Dict, Optional
from qdrant_distributed.config import MySQLManager
from qdrant_distributed.models.peer import PeerInfo
from qdrant_distributed.models.shard import ShardInfo
from datetime import datetime
import json


class MySQLService:
    def __init__(self, mysql_manager: MySQLManager = None):
        self.mysql_manager = mysql_manager or MySQLManager()
    
    def save_peers(self, peers: List[PeerInfo]):
        """
        Save peers to MySQL.
        
        Args:
            peers: List of PeerInfo objects to save
        """
        try:
            if self.mysql_manager.connection is None:
                raise ValueError("Database not initialized")
            
            cursor = self.mysql_manager.connection.cursor()
            
            try:
                # Generate snapshot ID (unix timestamp in milliseconds)
                timestamp = datetime.now()
                snapshot_id = int(timestamp.timestamp() * 1000)
                
                # Insert peers and shards with the same snapshot_id
                for peer in peers:
                    # Insert peer
                    cursor.execute(
                        """INSERT INTO peers (snapshot_id, peer_id, uri, created_at) 
                           VALUES (%s, %s, %s, %s)""",
                        (snapshot_id, peer.peer_id, peer.uri, timestamp)
                    )
                    
                    # Insert shards for this peer
                    for shard in peer.local_shards:
                        cursor.execute(
                            """INSERT INTO shards (snapshot_id, peer_id, shard_id, points_count, state, created_at)
                               VALUES (%s, %s, %s, %s, %s, %s)""",
                            (snapshot_id, peer.peer_id, shard.shard_id, shard.points_count, shard.state.value, timestamp)
                        )
                
                self.mysql_manager.connection.commit()
            except Exception as e:
                self.mysql_manager.connection.rollback()
                raise e
            finally:
                cursor.close()
        except Exception as e:
            print(f"Error saving peers: {e}")
            raise e

    def get_latest_peers(self) -> Optional[Dict]:
        """
        Get the latest peers document from MySQL.
        
        Returns:
            Dictionary containing timestamp and peers list, or None if not found
        """
        if self.mysql_manager.connection is None:
            raise ValueError("Database not initialized")
        
        # Use dictionary=True for dictionary results (works with both C and pure Python implementation)
        cursor = self.mysql_manager.connection.cursor(dictionary=True)
        
        try:
            # Get latest snapshot_id
            cursor.execute("""
                SELECT MAX(snapshot_id) as snapshot_id, MAX(created_at) as timestamp 
                FROM peers
            """)
            snapshot = cursor.fetchone()
            
            if not snapshot or snapshot['snapshot_id'] is None:
                return None
            
            snapshot_id = snapshot['snapshot_id']
            timestamp = snapshot['timestamp']
            
            # Get peers for this snapshot
            cursor.execute("""
                SELECT DISTINCT peer_id, uri 
                FROM peers 
                WHERE snapshot_id = %s
            """, (snapshot_id,))
            peers_data = cursor.fetchall()
            
            # Get shards for each peer in this snapshot
            peers_list = []
            for peer_data in peers_data:
                peer_id = peer_data['peer_id']
                
                cursor.execute("""
                    SELECT shard_id, points_count, state 
                    FROM shards 
                    WHERE snapshot_id = %s AND peer_id = %s
                """, (snapshot_id, peer_id))
                shards_data = cursor.fetchall()
                
                shards = [ShardInfo.from_dict(shard) for shard in shards_data]
                
                peer_dict = {
                    "peer_id": peer_id,
                    "uri": peer_data['uri'] or "",
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

