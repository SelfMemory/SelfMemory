import chromadb
import math
import os
import sys
from pathlib import Path

def get_db_path():
    """Get absolute path for database directory"""
    current_dir = Path(__file__).parent.absolute()
    db_path = current_dir / "db"
    return str(db_path)

def ensure_db_directory():
    """Ensure database directory exists with proper permissions"""
    db_path = get_db_path()
    try:
        os.makedirs(db_path, mode=0o755, exist_ok=True)
        # Test write permissions
        test_file = os.path.join(db_path, ".write_test")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        return True
    except (OSError, PermissionError) as e:
        print(f"Warning: Cannot write to database directory {db_path}: {e}", file=sys.stderr)
        return False

def create_chroma_client():
    """Create ChromaDB client with fallback to in-memory if persistent fails"""
    # First try to create persistent client
    if ensure_db_directory():
        try:
            db_path = get_db_path()
            print(f"Attempting to create persistent client at: {db_path}", file=sys.stderr)
            client = chromadb.PersistentClient(path=db_path)
            print("Successfully created persistent ChromaDB client", file=sys.stderr)
            return client, "persistent"
        except Exception as e:
            print(f"Failed to create persistent client: {e}", file=sys.stderr)
            print("Falling back to in-memory client", file=sys.stderr)
    
    # Fallback to in-memory client
    try:
        client = chromadb.Client()
        print("Successfully created in-memory ChromaDB client", file=sys.stderr)
        return client, "memory"
    except Exception as e:
        print(f"Failed to create in-memory client: {e}", file=sys.stderr)
        raise RuntimeError(f"Cannot create ChromaDB client: {e}")

# Create the client with error handling
try:
    client, client_type = create_chroma_client()
    collection = client.get_or_create_collection(name="shrijayan")
    print(f"ChromaDB collection 'shrijayan' ready using {client_type} storage", file=sys.stderr)
except Exception as e:
    print(f"Critical error initializing ChromaDB: {e}", file=sys.stderr)
    # Create a mock collection for graceful degradation
    class MockCollection:
        def add(self, ids, documents):
            print("Warning: Using mock collection - data not persisted", file=sys.stderr)
            return "Mock: Added to Memory Successfully!"
        
        def query(self, query_texts, n_results=3):
            print("Warning: Using mock collection - no data to retrieve", file=sys.stderr)
            return {"documents": [["Mock: No Memory Found"]]}
    
    collection = MockCollection()
    print("Using mock collection due to ChromaDB initialization failure", file=sys.stderr)
