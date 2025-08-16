# #!/usr/bin/env python3
# """
# Test script to verify the API key validation fix for managed service.

# This script tests that the Inmry client can now properly validate API keys
# using the correct /v1/users/current endpoint instead of the broken /v1/ping/ endpoint.
# """

# import os
# import sys
# from inmemory import Inmry


# def test_managed_service_fix():
#     """Test that the managed service API key validation works correctly."""

#     print("=== Testing Fixed Managed Service ===")
#     print("Testing API key validation fix...")

#     # Test API key (get from environment or use placeholder)
#     api_key = os.getenv("INMEMORY_API_KEY", "im_your_api_key_here")

#     try:
#         print(f"\n1. Testing Inmry initialization with API key...")
#         print(f"   API Key: {api_key[:15]}...")
#         print(f"   Host: http://localhost:8081")

#         # This should now work with the fix!
#         inmry = Inmry(api_key=api_key, host="http://localhost:8081")

#         print("✅ Inmry client initialized successfully!")
#         print(f"   User ID: {inmry.user_id}")
#         print(f"   User Info: {inmry.user_info}")

#         # Test a basic operation
#         print(f"\n2. Testing health check...")
#         health = inmry.health_check()
#         print(f"✅ Health check successful: {health}")

#         # Test adding a memory
#         print(f"\n3. Testing memory addition...")
#         result = inmry.add(
#             memory_content="Test memory after API key validation fix",
#             user_id=inmry.user_info.get("user_id", "test_user"),
#             tags="test,bug-fix,validation",
#         )
#         print(f"✅ Memory added: {result}")

#         # Test searching
#         print(f"\n4. Testing memory search...")
#         search_results = inmry.search(
#             query="validation fix", user_id=inmry.user_info.get("user_id", "test_user")
#         )
#         print(f"✅ Search completed: {len(search_results.get('results', []))} results")

#         # Clean up
#         inmry.close()

#         print(
#             f"\n🎉 All tests passed! The API key validation fix is working correctly."
#         )
#         return True

#     except ValueError as e:
#         if "API key validation failed" in str(e):
#             print(f"❌ API key validation still failing: {e}")
#             print("\nPossible issues:")
#             print("1. API server not running on localhost:8000")
#             print("2. API key is invalid or expired")
#             print("3. /v1/users/current endpoint not working")
#             return False
#         else:
#             print(f"❌ Unexpected error: {e}")
#             return False

#     except Exception as e:
#         print(f"❌ Unexpected error: {e}")
#         return False


# def test_comparison():
#     """Show the before/after comparison."""
#     print(f"\n=== Fix Summary ===")
#     print("BEFORE (Broken):")
#     print("  Client called: /v1/ping/ (public endpoint, no auth)")
#     print("  Expected: user_info in response")
#     print("  Result: 404 Not Found or missing user_info")

#     print("\nAFTER (Fixed):")
#     print("  Client calls: /v1/users/current (authenticated endpoint)")
#     print("  Returns: actual user info with authentication")
#     print("  Result: ✅ API key validation works correctly")


# if __name__ == "__main__":
#     print("Starting API key validation fix test...\n")

#     # Test the fix
#     success = test_managed_service_fix()

#     # Show comparison
#     test_comparison()

#     if success:
#         print(f"\n✅ SUCCESS: Your inmemory package is working correctly!")
#         print("You can now use both:")
#         print("- Self-hosted: Memory() - works offline")
#         print("- Managed: Inmry() - works with API server")
#         sys.exit(0)
#     else:
#         print(f"\n❌ Test failed. Check API server and key.")
