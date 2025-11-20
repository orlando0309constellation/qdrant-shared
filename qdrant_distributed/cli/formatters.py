"""
Output formatters for CLI display.
"""

from typing import Dict, List, Any


class ResultFormatter:
    """Formatter for CLI output display."""
    
    @staticmethod
    def print_header(title: str, width: int = 80) -> None:
        """Print a formatted header."""
        print("=" * width)
        print(title)
        print("=" * width)
    
    @staticmethod
    def print_operation_result(result: Dict[str, Any]) -> None:
        """
        Format and print operation result.
        
        Args:
            result: Operation result dictionary
        """
        ResultFormatter.print_header("✅ Operation completed successfully!")
        print(f"Status: {result.get('status')}")
        print(f"Result: {result.get('result')}")
        print(f"Time: {result.get('time', 0):.3f}s")
        
        if result.get('usage'):
            print("\n📊 Resource Usage:")
            usage = result.get('usage')
            if isinstance(usage, dict):
                for key, value in usage.items():
                    print(f"  {key}: {value}")
            else:
                print(f"  {usage}")
    
    @staticmethod
    def print_shard_list(peer_shards: Dict[int, List[Any]]) -> None:
        """
        Format and print shard list.
        
        Args:
            peer_shards: Dictionary of peer IDs to shard lists
        """
        ResultFormatter.print_header("✅ Successfully retrieved shard information from all peers!")
        print()
        
        if not peer_shards:
            print("⚠️  No peers found or no shard information available")
            return
        
        total_shards = 0
        total_points = 0
        
        for peer_id, shards in sorted(peer_shards.items()):
            print(f"📍 Peer {peer_id}:")
            print(f"   {'='*70}")
            
            if not shards:
                print("   No local shards")
            else:
                for shard in shards:
                    shard_id = shard.shard_id
                    points_count = shard.points_count
                    state = shard.state.value
                    total_shards += 1
                    total_points += points_count
                    
                    print(f"   ├─ Shard {shard_id}")
                    print(f"   │  ├─ Points: {points_count:,}")
                    print(f"   │  └─ State: {state}")
            
            print()
        
        print("=" * 80)
        print(f"📊 Summary:")
        print(f"   Total Peers: {len(peer_shards)}")
        print(f"   Total Local Shards: {total_shards}")
        print(f"   Total Points: {total_points:,}")
        print("=" * 80)
    
    @staticmethod
    def print_error(error_type: str, message: str, suggestions: List[str] = None) -> None:
        """
        Format and print error message.
        
        Args:
            error_type: Type of error
            message: Error message
            suggestions: Optional list of suggestions
        """
        print("=" * 80)
        print(f"❌ {error_type}")
        print("=" * 80)
        print(f"Error: {message}")
        
        if suggestions:
            print("\nSuggestions:")
            for suggestion in suggestions:
                print(f"  - {suggestion}")

