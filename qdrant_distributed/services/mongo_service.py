from typing import List, Dict
from qdrant_distributed.config import MongoManager
from qdrant_distributed.models.peer import PeerInfo
from qdrant_distributed.models.shard import ShardInfo
from datetime import datetime


class MongoService:
    def __init__(self, mongo_manager: MongoManager = None):
        self.mongo_manager = mongo_manager or MongoManager()
    
    def save_peers(self, peers: List[PeerInfo]):
        """
        Save peers to MongoDB.
        
        Args:
            peers: List of PeerInfo objects to save
        """
        try:
            if self.mongo_manager.db is None:
                raise ValueError("Database not initialized")
            peers_logs = self.mongo_manager.db.get_collection("peers_logs")
            payload = {
                "timestamp": datetime.now(),
                "peers": [peer.to_dict() for peer in peers]
            }
            peers_logs.insert_one(payload)
        except Exception as e:
            print(f"Error saving peers: {e}")
            raise e

    def get_latest_peers(self):
        """
        Get the latest peers document from MongoDB.
        
        Returns:
            Dictionary containing timestamp and peers list, or None if not found
        """
        if self.mongo_manager.db is None:
            raise ValueError("Database not initialized")
        peers_logs = self.mongo_manager.db.get_collection("peers_logs")
        return peers_logs.find_one(sort=[("timestamp", -1)])
    
    def get_latest_peers_as_dict(self) -> Dict[int, List[ShardInfo]]:
        """
        Get the latest peers from MongoDB and convert to the format used by list_all_shards.
        
        Returns:
            Dictionary mapping peer_id to list of ShardInfo objects
        
        Raises:
            ValueError: If no peer data found in MongoDB
        """
        latest_doc = self.get_latest_peers()
        if latest_doc is None or "peers" not in latest_doc:
            raise ValueError("No peer data found in MongoDB")
        
        # Convert MongoDB document to Dict[int, List[ShardInfo]]
        peer_shards: Dict[int, List[ShardInfo]] = {}
        for peer_data in latest_doc["peers"]:
            peer_id = peer_data["peer_id"]
            shards = [ShardInfo.from_dict(shard_dict) for shard_dict in peer_data.get("local_shards", [])]
            peer_shards[peer_id] = shards
        
        return peer_shards
    
    def get_latest_peer_uris(self) -> Dict[int, str]:
        """
        Get the latest peer URIs from MongoDB.
        
        Returns:
            Dictionary mapping peer_id to URI string
        
        Raises:
            ValueError: If no peer data found in MongoDB
        """
        latest_doc = self.get_latest_peers()
        if latest_doc is None or "peers" not in latest_doc:
            raise ValueError("No peer data found in MongoDB")
        
        # Extract URIs from MongoDB document
        peer_uris: Dict[int, str] = {}
        for peer_data in latest_doc["peers"]:
            peer_id = peer_data["peer_id"]
            uri = peer_data.get("uri", "")
            peer_uris[peer_id] = uri
        
        return peer_uris