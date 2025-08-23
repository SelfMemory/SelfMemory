"""
Command Line Interface for InMemory.

Provides easy-to-use commands for starting servers, managing data,
and working with different deployment modes.
"""

import argparse
import logging
import sys
from pathlib import Path

from .config import (
    create_sample_configs,
    load_config,
)
from .memory import Memory

logger = logging.getLogger(__name__)


def serve_command(args):
    """Start the InMemory API server."""
    try:
        import uvicorn

        from .api.server import create_app

        # Import to verify dependencies are available
        create_app()
    except ImportError:
        print("❌ Server dependencies not installed. Run: pip install inmemory[server]")
        sys.exit(1)

    # Override configuration with CLI arguments
    if args.storage_type:
        import os

        os.environ["INMEMORY_STORAGE_TYPE"] = args.storage_type

    if args.data_dir:
        import os

        os.environ["INMEMORY_DATA_DIR"] = args.data_dir

    if args.mongodb_uri:
        import os

        os.environ["MONGODB_URI"] = args.mongodb_uri

    print(f"🚀 Starting InMemory API server on {args.host}:{args.port}")
    print(f"📊 Storage backend: {args.storage_type or 'auto-detected'}")
    print(f"🔗 API docs: http://{args.host}:{args.port}/docs")

    # Start server
    uvicorn.run(
        "inmemory.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.debug else "info",
    )


def init_command(args):
    """Initialize InMemory in current directory."""
    current_dir = Path.cwd()

    print(f"🏗️  Initializing InMemory in: {current_dir}")

    # Create sample configuration files
    try:
        create_sample_configs()
        print("✅ Sample configuration files created in ~/.inmemory/")
        print("   - config-simple.yaml (file-based storage)")
        print("   - config-enterprise.yaml (MongoDB + OAuth)")
    except Exception as e:
        logger.warning(f"Failed to create sample configs: {e}")

    # Test basic functionality
    try:
        memory = Memory()
        test_user = args.user or "test_user"

        # Test adding a memory
        result = memory.add("InMemory initialization test", user_id=test_user)
        if result.get("success", False):
            print(f"✅ Successfully added test memory for user: {test_user}")

            # Test searching
            search_results = memory.search("initialization", user_id=test_user)
            if search_results.get("results"):
                print(
                    f"✅ Search working - found {len(search_results['results'])} results"
                )
            else:
                print("⚠️  Search returned no results")
        else:
            print(f"❌ Failed to add test memory: {result}")

        # Show statistics
        stats = memory.get_user_stats(test_user)
        print(f"📊 User stats: {stats.get('memory_count', 0)} memories")
        print(f"🗄️  Storage backend: {stats.get('storage_backend', 'unknown')}")

        memory.close()

    except Exception as e:
        print(f"❌ Initialization test failed: {e}")
        print("💡 Try: pip install inmemory[full] for all dependencies")


def test_command(args):
    """Test InMemory functionality."""
    print("🧪 Testing InMemory functionality...")

    try:
        # Test with specified storage type or auto-detect
        memory = (
            Memory(storage_type=args.storage_type) if args.storage_type else Memory()
        )

        test_user = args.user or "cli_test_user"

        # Add test memories
        test_memories = [
            "I love pizza and hate broccoli",
            "Meeting with Sarah and Mike about project X",
            "Dentist appointment tomorrow at 3pm",
            "Favorite color is blue, favorite season is autumn",
        ]

        print(f"📝 Adding {len(test_memories)} test memories for user: {test_user}")

        for i, memory_text in enumerate(test_memories, 1):
            result = memory.add(memory_text, user_id=test_user)
            if result.get("success", False):
                print(f"  ✅ Memory {i} added successfully")
            else:
                print(f"  ❌ Memory {i} failed: {result}")

        # Test different search methods
        print("\n🔍 Testing search functionality:")

        search_tests = [
            ("pizza", "general search"),
            ("project", "work-related search"),
            ("tomorrow", "temporal search"),
        ]

        for query, description in search_tests:
            results = memory.search(query, user_id=test_user, limit=3)
            result_count = len(results.get("results", []))
            print(f"  🔸 {description}: {result_count} results for '{query}'")

        # Test user statistics
        stats = memory.get_user_stats(test_user)
        print("\n📊 Final statistics:")
        print(f"  👤 User: {test_user}")
        print(f"  💾 Storage: {stats.get('storage_backend', 'unknown')}")
        print(f"  📝 Memories: {stats.get('memory_count', 0)}")

        memory.close()
        print("✅ All tests completed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("💡 Make sure Qdrant is running and dependencies are installed")


def config_command(args):
    """Show current configuration."""
    try:
        config = load_config()

        print("⚙️  Current InMemory Configuration:")
        print(f"📁 Storage Type: {config.storage.type}")

        if config.storage.type == "file":
            print(f"📂 Data Directory: {config.storage.path}")
        elif config.storage.type == "mongodb":
            print(f"🗄️  MongoDB URI: {config.storage.mongodb_uri}")

        print(f"🔐 Auth Type: {config.auth.type}")
        print(f"🗂️  Qdrant Host: {config.qdrant.host}:{config.qdrant.port}")
        print(f"🤖 Embedding Provider: {config.embedding.provider}")
        print(f"🎯 Embedding Model: {config.embedding.model}")

        if args.verbose:
            print("\n📋 Full Configuration:")
            import json

            print(json.dumps(config.to_dict(), indent=2))

    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")


def stats_command(args):
    """Show storage statistics."""
    try:
        memory = (
            Memory(storage_type=args.storage_type) if args.storage_type else Memory()
        )

        print("📊 InMemory Storage Statistics:")

        if hasattr(memory.store, "get_stats"):
            stats = memory.store.get_stats()

            print(f"🗄️  Storage Type: {stats.get('storage_type', 'unknown')}")
            print(f"👥 Total Users: {stats.get('total_users', 0)}")
            print(f"🔑 Total API Keys: {stats.get('total_api_keys', 0)}")
            print(f"🟢 Active API Keys: {stats.get('active_api_keys', 0)}")

            if args.verbose:
                print("\n📋 Detailed Statistics:")
                import json

                print(json.dumps(stats, indent=2, default=str))
        else:
            print("⚠️  Statistics not available for this storage backend")

        memory.close()

    except Exception as e:
        print(f"❌ Failed to get statistics: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="inmemory",
        description="InMemory - Enhanced Memory Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  inmemory serve                    # Start API server (auto-detect mode)
  inmemory serve --storage file     # Start with file backend
  inmemory serve --storage mongodb  # Start with MongoDB backend
  inmemory init                     # Initialize in current directory
  inmemory test                     # Test functionality
  inmemory config                   # Show current configuration
  inmemory stats                    # Show storage statistics
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start API server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    serve_parser.add_argument(
        "--port", type=int, default=8081, help="Port to listen on"
    )
    serve_parser.add_argument(
        "--storage-type", choices=["file", "mongodb"], help="Storage backend type"
    )
    serve_parser.add_argument("--data-dir", help="Data directory (file storage)")
    serve_parser.add_argument("--mongodb-uri", help="MongoDB URI")
    serve_parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload"
    )
    serve_parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    serve_parser.set_defaults(func=serve_command)

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize InMemory")
    init_parser.add_argument("--user", default="cli_user", help="Test user ID")
    init_parser.set_defaults(func=init_command)

    # Test command
    test_parser = subparsers.add_parser("test", help="Test functionality")
    test_parser.add_argument(
        "--storage-type", choices=["file", "mongodb"], help="Storage backend to test"
    )
    test_parser.add_argument("--user", default="cli_test_user", help="Test user ID")
    test_parser.set_defaults(func=test_command)

    # Config command
    config_parser = subparsers.add_parser("config", help="Show configuration")
    config_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show full config"
    )
    config_parser.set_defaults(func=config_command)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.add_argument(
        "--storage-type", choices=["file", "mongodb"], help="Storage backend type"
    )
    stats_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed stats"
    )
    stats_parser.set_defaults(func=stats_command)

    # Parse arguments
    args = parser.parse_args()

    # Set up logging
    level = logging.DEBUG if getattr(args, "debug", False) else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Execute command
    if hasattr(args, "func"):
        try:
            args.func(args)
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Command failed: {e}")
            print(f"❌ Command failed: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
