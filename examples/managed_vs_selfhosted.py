"""
Examples showing the difference between managed (Inmry) and self-hosted (Memory) solutions.

This demonstrates the two deployment options for InMemory:
1. Managed solution using Inmry (connects to hosted API)
2. Self-hosted solution using Memory (runs locally)
"""

from inmemory import Inmry, Memory


def selfhosted_example():
    """Example using self-hosted Memory class."""
    print("=== Self-Hosted Example ===")

    # Initialize self-hosted memory (no API key needed)
    memory = Memory()

    # Add some memories - CLEAN API with NO user_id needed!
    result = memory.add(
        memory_content="I had lunch with Sarah today at the Italian restaurant",
        tags="food,meeting",
        people_mentioned="Sarah",
        topic_category="personal",
    )
    print(f"Added memory: {result}")

    result = memory.add(
        memory_content="Completed the quarterly report for Q3 2024",
        tags="work,report",
        topic_category="business",
    )
    print(f"Added memory: {result}")

    # Search memories - CLEAN API with NO user_id needed!
    results = memory.search("lunch")
    print(f"Search results: {len(results['results'])} memories found")
    for mem in results["results"]:
        print(f"  - {mem.get('content', 'N/A')}")

    # Get all memories - CLEAN API with NO user_id needed!
    all_memories = memory.get_all()
    print(f"Total memories: {len(all_memories['results'])}")

    print("Self-hosted example completed!\n")


def managed_example():
    """Example using managed Inmry class."""
    print("=== Managed Solution Example ===")

    # For this example, we'll simulate having an API key
    # In real usage, you'd set: os.environ["INMEM_API_KEY"] = "your-api-key"

    # Note: This will fail without a real API server running
    # This is just to show the usage pattern

    try:
        # Initialize managed client (requires API key)
        # os.environ["INMEM_API_KEY"] = "your-api-key"  # Set your API key
        inmry = Inmry()  # Will look for INMEM_API_KEY environment variable

        # Add some memories - CLEAN API with NO user_id needed!
        result = inmry.add(
            memory_content="Meeting with the development team about the new features",
            tags="work,meeting,development",
            people_mentioned="Bob,Charlie",
            topic_category="business",
        )
        print(f"Added memory: {result}")

        # Search memories - CLEAN API with NO user_id needed!
        results = inmry.search("development")
        print(f"Search results: {len(results['results'])} memories found")

        # Get user stats - user derived from API key
        stats = inmry.get_user_stats()
        print(f"User stats: {stats}")

        print("Managed example completed!")

    except ValueError as e:
        print(f"Managed example skipped: {e}")
        print("To use the managed solution:")
        print(
            "1. Set environment variable: os.environ['INMEM_API_KEY'] = 'your-api-key'"
        )
        print("2. Ensure the API server is running")
        print("3. Get an API key from the dashboard or API endpoint")


def compare_interfaces():
    """Show that both solutions have the same interface."""
    print("=== Interface Comparison ===")

    print("Self-hosted initialization:")
    print("  memory = Memory()  # No API key needed")

    print("\nManaged initialization:")
    print("  os.environ['INMEM_API_KEY'] = 'your-api-key'")
    print("  inmry = Inmry()  # API key from environment")

    print("\nBoth have identical CLEAN methods (NO user_id needed!):")
    methods = [
        "add(memory_content, ...)",  # No user_id needed!
        "search(query, ...)",  # No user_id needed!
        "get_all(...)",  # No user_id needed!
        "delete(memory_id)",  # No user_id needed!
        "delete_all()",  # No user_id needed!
        "temporal_search(temporal_query, ...)",  # No user_id needed!
        "search_by_tags(tags, ...)",  # No user_id needed!
        "search_by_people(people, ...)",  # No user_id needed!
        "get_user_stats()",  # No user_id needed! (managed: derived from API key)
        "health_check()",
    ]

    for method in methods:
        print(f"  - {method}")

    print("\nKey differences:")
    print("- Memory: Runs locally, stores data in local files/database")
    print("- Inmry: Connects to hosted API, data managed in the cloud")
    print("- Memory: Zero setup, full control")
    print("- Inmry: Requires API key, managed service benefits")


def deployment_options():
    """Show deployment options."""
    print("=== Deployment Options ===")

    print("Open Source (Self-Hosted):")
    print("- Full control and customization")
    print("- Host on your own infrastructure")
    print("- No API keys or external dependencies")
    print("- Supports file-based or MongoDB storage")
    print("- Perfect for privacy-sensitive applications")

    print("\nManaged Service:")
    print("- No infrastructure management needed")
    print("- Automatic scaling and updates")
    print("- Dashboard for user management")
    print("- API key authentication")
    print("- Usage analytics and monitoring")
    print("- Perfect for getting started quickly")


if __name__ == "__main__":
    # Run examples
    selfhosted_example()
    managed_example()
    compare_interfaces()
    deployment_options()
