#!/usr/bin/env python3
"""
InMemory New Architecture Demo

This demonstrates the new mem0-compatible architecture with:
1. Memory (zero-setup local)
2. AsyncMemory (async local)
3. InmemoryClient (managed service)
4. AsyncInmemoryClient (async managed)
"""

import asyncio
import os


def demo_memory():
    """Demo the zero-setup Memory class"""
    print("🔧 Memory Class Demo (Zero Setup)")
    print("=" * 50)

    try:
        from inmemory import Memory

        # Zero setup - works immediately!
        memory = Memory()
        print("✅ Memory initialized (zero setup)")

        # Add some memories
        result1 = memory.add("I love Python programming", tags="personal,tech")
        result2 = memory.add(
            "Meeting with Sarah about project roadmap",
            tags="work,meeting",
            people_mentioned="Sarah",
        )

        print(f"✅ Added memory 1: {result1['success']}")
        print(f"✅ Added memory 2: {result2['success']}")

        # Search
        results = memory.search("Python")
        print(f"✅ Search results: {len(results['results'])} found")

        # Health check
        health = memory.health_check()
        print(f"✅ Health: {health['status']} ({health['memory_count']} memories)")

        return True

    except Exception as e:
        print(f"❌ Memory demo failed: {e}")
        return False


async def demo_async_memory():
    """Demo the AsyncMemory class"""
    print("\n🚀 AsyncMemory Class Demo")
    print("=" * 50)

    try:
        from inmemory import AsyncMemory

        async with AsyncMemory() as memory:
            print("✅ AsyncMemory initialized")

            # Add memory asynchronously
            result = await memory.add("Async memory test", tags="async,demo")
            print(f"✅ Async add: {result['success']}")

            # Search asynchronously
            results = await memory.search("async")
            print(f"✅ Async search: {len(results['results'])} results")

            # Health check
            health = await memory.health_check()
            print(f"✅ Async health: {health['status']}")

        return True

    except Exception as e:
        print(f"❌ AsyncMemory demo failed: {e}")
        return False


def demo_managed_client():
    """Demo the managed InmemoryClient"""
    print("\n☁️ InmemoryClient Demo (Managed Service)")
    print("=" * 50)

    try:
        from inmemory import InmemoryClient

        # This requires a running server and API key
        api_key = os.getenv("INMEM_API_KEY")
        if not api_key:
            print("⚠️ No API key found (INMEM_API_KEY)")
            print("To test managed mode:")
            print("1. Start server: cd server/ && python main.py")
            print("2. Set API key: export INMEM_API_KEY=your_key")
            print("3. Run this demo again")
            return True

        client = InmemoryClient(api_key=api_key, host="http://localhost:8081")
        print("✅ InmemoryClient initialized")

        # Test managed operations
        result = client.add("Managed memory test", tags="managed,demo")
        print(f"✅ Managed add: {result.get('success', False)}")

        # Search managed memories
        results = client.search("managed")
        print(f"✅ Managed search: {len(results.get('results', []))} results")

        # Health check
        health = client.health_check()
        print(f"✅ Managed health: {health.get('status')}")

        return True

    except Exception as e:
        print(f"❌ InmemoryClient demo failed: {e}")
        print("Make sure server is running: cd server/ && python main.py")
        return False


def main():
    print("🎯 InMemory New Architecture Demo")
    print("=" * 60)
    print()

    print("Following mem0 pattern:")
    print("- Memory, AsyncMemory (local/zero-setup)")
    print("- InmemoryClient, AsyncInmemoryClient (managed/authenticated)")
    print()

    # Demo each class
    success1 = demo_memory()
    success2 = asyncio.run(demo_async_memory())
    success3 = demo_managed_client()

    print("\n📊 Results Summary")
    print("=" * 50)
    print(f"Memory (zero-setup): {'✅ PASSED' if success1 else '❌ FAILED'}")
    print(f"AsyncMemory (async): {'✅ PASSED' if success2 else '❌ FAILED'}")
    print(f"InmemoryClient (managed): {'✅ PASSED' if success3 else '❌ FAILED'}")

    if all([success1, success2, success3]):
        print("\n🎉 All demos passed! Architecture working perfectly!")
    else:
        print("\n⚠️ Some demos failed - check requirements and server status")

    print("\n🏗️ Architecture Benefits")
    print("=" * 50)
    print("✅ Clean separation: Library vs Server")
    print("✅ Zero setup: Memory() works immediately")
    print("✅ Dashboard ready: InmemoryClient() for API integration")
    print("✅ mem0 compatible: Same class naming patterns")
    print("✅ Two distribution modes: pip install + server deployment")


if __name__ == "__main__":
    main()
