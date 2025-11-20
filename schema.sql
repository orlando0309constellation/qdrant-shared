-- Qdrant Manager MySQL Schema
-- This script creates the necessary tables for storing Qdrant cluster peer information

-- Create database (optional - uncomment if needed)
-- CREATE DATABASE IF NOT EXISTS qdrant_manager;
-- USE qdrant_manager;

-- Table: peers
-- Stores peer information with snapshot tracking
-- Each snapshot represents a point-in-time capture of the cluster state
CREATE TABLE IF NOT EXISTS peers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id BIGINT NOT NULL COMMENT 'Unix timestamp in milliseconds to group related records',
    peer_id BIGINT NOT NULL COMMENT 'Qdrant peer ID',
    uri VARCHAR(500) COMMENT 'Peer URI/endpoint',
    created_at DATETIME NOT NULL COMMENT 'Timestamp when this record was created',
    INDEX idx_snapshot_id (snapshot_id),
    INDEX idx_peer_id (peer_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Stores Qdrant peer information snapshots';

-- Table: shards
-- Stores shard information for each peer
CREATE TABLE IF NOT EXISTS shards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id BIGINT NOT NULL COMMENT 'Links to the same snapshot as peers table',
    peer_id BIGINT NOT NULL COMMENT 'Qdrant peer ID that owns this shard',
    shard_id INT NOT NULL COMMENT 'Shard ID within the collection',
    points_count BIGINT NOT NULL COMMENT 'Number of points in this shard',
    state VARCHAR(50) NOT NULL COMMENT 'Shard state (e.g., Active, Dead, Partial, Replica)',
    created_at DATETIME NOT NULL COMMENT 'Timestamp when this record was created',
    INDEX idx_snapshot_id (snapshot_id),
    INDEX idx_peer_id (peer_id),
    INDEX idx_shard_id (shard_id),
    INDEX idx_created_at (created_at),
    INDEX idx_snapshot_peer (snapshot_id, peer_id) COMMENT 'Composite index for faster queries'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Stores Qdrant shard information';

-- Optional: View to get the latest snapshot easily
CREATE OR REPLACE VIEW latest_snapshot AS
SELECT 
    p.peer_id,
    p.uri,
    s.shard_id,
    s.points_count,
    s.state,
    p.created_at,
    p.snapshot_id
FROM peers p
LEFT JOIN shards s ON p.snapshot_id = s.snapshot_id AND p.peer_id = s.peer_id
WHERE p.snapshot_id = (SELECT MAX(snapshot_id) FROM peers);

-- Optional: View to get snapshot summary statistics
CREATE OR REPLACE VIEW snapshot_summary AS
SELECT 
    snapshot_id,
    MAX(created_at) as created_at,
    COUNT(DISTINCT peer_id) as peer_count,
    COUNT(DISTINCT shard_id) as shard_count,
    SUM(points_count) as total_points
FROM shards
GROUP BY snapshot_id
ORDER BY snapshot_id DESC;

-- Example queries:

-- Get the latest snapshot
-- SELECT * FROM latest_snapshot;

-- Get all snapshots with statistics
-- SELECT * FROM snapshot_summary;

-- Get a specific snapshot by snapshot_id
-- SELECT p.peer_id, p.uri, s.shard_id, s.points_count, s.state
-- FROM peers p
-- LEFT JOIN shards s ON p.snapshot_id = s.snapshot_id AND p.peer_id = s.peer_id
-- WHERE p.snapshot_id = <your_snapshot_id>;

-- Clean up old snapshots (keep only last 30 days)
-- DELETE FROM peers WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
-- DELETE FROM shards WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);

