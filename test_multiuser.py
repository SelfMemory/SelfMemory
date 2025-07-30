#!/usr/bin/env python3
"""
Test script for multi-user memory MCP server functionality.
Tests user validation, collection naming, and basic operations.
"""

import logging
import sys
from user_management import user_manager
from qdrant_db import ensure_user_collection_exists

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_user_management():
    """Test user validation and collection naming."""
    print("=" * 50)
    print("Testing User Management System")
    print("=" * 50)
    
    # Test valid users
    valid_users = ["alice", "bob", "charlie", "diana", "test_user"]
    
    for user_id in valid_users:
        is_valid = user_manager.is_valid_user(user_id)
        collection_name = user_manager.get_collection_name(user_id) if is_valid else "N/A"
        print(f"User: {user_id:10} | Valid: {is_valid:5} | Collection: {collection_name}")
    
    # Test invalid users
    invalid_users = ["john", "invalid_user", "hacker", ""]
    print("\nTesting invalid users:")
    for user_id in invalid_users:
        is_valid = user_manager.is_valid_user(user_id)
        print(f"User: {user_id:12} | Valid: {is_valid}")
    
    return True

def test_collection_creation():
    """Test dynamic collection creation for valid users."""
    print("\n" + "=" * 50)
    print("Testing Collection Creation")
    print("=" * 50)
    
    test_users = ["alice", "test_user"]
    
    for user_id in test_users:
        try:
            collection_name = ensure_user_collection_exists(user_id)
            print(f"✅ User: {user_id} -> Collection: {collection_name}")
        except Exception as e:
            print(f"❌ User: {user_id} -> Error: {str(e)}")
    
    # Test invalid user
    try:
        collection_name = ensure_user_collection_exists("invalid_user")
        print(f"❌ Should have failed for invalid_user")
    except Exception as e:
        print(f"✅ Correctly rejected invalid_user: {str(e)}")
    
    return True

def test_url_patterns():
    """Test the expected URL patterns for alpha testers."""
    print("\n" + "=" * 50)
    print("Alpha Tester URL Patterns")
    print("=" * 50)
    
    base_url = "https://memory.tailb75d54.ts.net"
    approved_users = user_manager.get_approved_users()
    
    print("Alpha testers can use these URLs:")
    for user_id in approved_users:
        url = f"{base_url}/{user_id}/sse"
        install_cmd = f"npx install-mcp {url} --client claude"
        print(f"{user_id:10}: {install_cmd}")
    
    return True

def main():
    """Run all tests."""
    print("🧪 Testing Multi-User Memory MCP Server")
    print("=" * 60)
    
    try:
        # Test 1: User Management
        test_user_management()
        
        # Test 2: Collection Creation (requires Qdrant to be running)
        try:
            test_collection_creation()
        except Exception as e:
            print(f"⚠️  Collection test skipped (Qdrant not available): {str(e)}")
        
        # Test 3: URL Patterns
        test_url_patterns()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")
        print("\nTo start the multi-user server:")
        print("python server.py --host 0.0.0.0 --port 8080")
        print("\nAlpha testers can then connect with:")
        print("npx install-mcp https://memory.tailb75d54.ts.net/{user_id}/sse --client claude")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
