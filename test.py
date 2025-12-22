import requests
import time
def recover_collection_from_authenticated_snapshot(
    qdrant_api_url: str,           # e.g., "http://localhost:6333"
    snapshot_url: str,             # your snapshot URL
    collection_name: str,          # NEW collection name to create
    qdrant_api_key: str,
    timeout: int = 1800,
):
    headers = {"api-key": qdrant_api_key}
    coll_url = f"{qdrant_api_url.rstrip('/')}/collections/{collection_name}"

    # Step 1: Trigger recovery directly from URL into NEW collection
    # The collection will be CREATED by Qdrant during recovery if it doesn't exist
    # Use wait=false to avoid gateway timeout - recovery happens asynchronously
    recover_url = f"{qdrant_api_url}/collections/{collection_name}/snapshots/recover?wait=false"
    payload = {
        "location": snapshot_url,
        "priority": "snapshot",  # Ensures snapshot data is used as source of truth
        "api_key": qdrant_api_key  # API key for Qdrant to use when downloading the snapshot
    }
    print(f"🔄 Recovering snapshot into new collection '{collection_name}' (async mode)...")
    r = requests.put(recover_url, json=payload, headers=headers)
    if not r.ok:
        print(f"❌ Error response: {r.status_code}")
        print(f"📄 Response body: {r.text}")
    r.raise_for_status()
    print("✅ Recovery triggered from snapshot URL (running in background).")

    # Step 2: Wait for collection to be ready
    for _ in range(timeout // 5):
        try:
            resp = requests.get(coll_url, headers=headers)
            if resp.ok and resp.json().get("result", {}).get("status") in ("green", "ok"):
                print("✅ Recovery complete!")
                return True
        except:
            pass
        time.sleep(5)
    raise TimeoutError("Recovery timeout")

# Configuration
QDRANT_API_URL = "https://qdrant-1.myauxilium.tech:8080"  # Your Qdrant REST API endpoint
QDRANT_API_KEY = "77980315-f0f5-4f52-9e66-5ee682d115e6"                # Same key used for snapshot access
COLLECTION_NAME = "shared_vectors_hybrid"
SNAPSHOT_URL = (
    "https://qdrant-1.myauxilium.tech:8080/collections/shared_vectors_hybrid/"
    "snapshots/shared_vectors_hybrid-201354977342616-2025-12-18-11-45-52.snapshot"
)

if __name__ == "__main__":
    try:
        success = recover_collection_from_authenticated_snapshot(
            qdrant_api_url=QDRANT_API_URL,
            snapshot_url=SNAPSHOT_URL,
            collection_name=COLLECTION_NAME,
            qdrant_api_key=QDRANT_API_KEY,
            timeout=3600,              # Allow up to 1 hour for recovery
        )
        if success:
            print(f"🎉 Recovery of '{COLLECTION_NAME}' completed successfully!")
        else:
            print("❌ Recovery failed (unexpected state).")
    except Exception as e:
        print(f"💥 Recovery failed with error: {e}")
        raise