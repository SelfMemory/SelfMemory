"""
Deployment utilities for InMemory API server.

This module provides utilities for deploying the managed InMemory API server
in various environments (development, staging, production).
"""

import logging
import os
import sys

import uvicorn
from fastapi import FastAPI

from .server import create_app


def setup_logging(level: str = "INFO", log_file: str | None = None):
    """Setup logging configuration for the API server."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    logging.info(f"Logging configured with level: {level}")


def load_environment_config():
    """Load configuration from environment variables."""
    config = {
        # Server configuration
        "host": os.getenv("INMEMORY_HOST", "0.0.0.0"),
        "port": int(os.getenv("INMEMORY_PORT", "8000")),
        "workers": int(os.getenv("INMEMORY_WORKERS", "1")),
        "reload": os.getenv("INMEMORY_RELOAD", "false").lower() == "true",
        # Logging
        "log_level": os.getenv("INMEMORY_LOG_LEVEL", "INFO"),
        "log_file": os.getenv("INMEMORY_LOG_FILE"),
        # Storage backend
        "storage_type": os.getenv("INMEMORY_STORAGE_TYPE", "file"),
        "mongodb_uri": os.getenv("INMEMORY_MONGODB_URI"),
        # Security
        "cors_origins": os.getenv("INMEMORY_CORS_ORIGINS", "*").split(","),
        "api_key_prefix": os.getenv("INMEMORY_API_KEY_PREFIX", "im_"),
        # Features
        "enable_docs": os.getenv("INMEMORY_ENABLE_DOCS", "true").lower() == "true",
        "max_memory_size": int(os.getenv("INMEMORY_MAX_MEMORY_SIZE", "1048576")),  # 1MB
    }

    return config


def validate_configuration(config: dict) -> bool:
    """Validate the deployment configuration."""
    errors = []

    # Check required MongoDB URI if using MongoDB
    if config["storage_type"] == "mongodb" and not config["mongodb_uri"]:
        errors.append("INMEMORY_MONGODB_URI is required when using MongoDB storage")

    # Validate port range
    if not (1 <= config["port"] <= 65535):
        errors.append(f"Invalid port: {config['port']}. Must be between 1 and 65535")

    # Validate workers count
    if config["workers"] < 1:
        errors.append(f"Invalid workers count: {config['workers']}. Must be at least 1")

    if errors:
        for error in errors:
            logging.error(f"Configuration error: {error}")
        return False

    return True


def create_production_app() -> FastAPI:
    """Create FastAPI app configured for production."""
    config = load_environment_config()

    if not validate_configuration(config):
        raise ValueError("Invalid configuration")

    # Setup logging
    setup_logging(config["log_level"], config["log_file"])

    # Create app
    app = create_app()

    # Update app configuration for production
    if not config["enable_docs"]:
        app.docs_url = None
        app.redoc_url = None

    # Add additional middleware or configuration as needed
    logging.info("Production app created successfully")
    return app


def run_development_server():
    """Run the API server in development mode."""
    config = load_environment_config()
    setup_logging(config["log_level"], config["log_file"])

    logging.info("Starting InMemory API server in development mode")
    logging.info(
        f"Server will be available at http://{config['host']}:{config['port']}"
    )
    logging.info("API documentation at /docs")

    app = create_app()

    uvicorn.run(
        app,
        host=config["host"],
        port=config["port"],
        reload=config["reload"],
        log_level=config["log_level"].lower(),
        access_log=True,
    )


def run_production_server():
    """Run the API server in production mode using Gunicorn."""
    try:
        import gunicorn.app.wsgiapp as wsgi
    except ImportError:
        logging.error("Gunicorn not installed. Install with: pip install gunicorn")
        sys.exit(1)

    config = load_environment_config()
    setup_logging(config["log_level"], config["log_file"])

    if not validate_configuration(config):
        sys.exit(1)

    logging.info("Starting InMemory API server in production mode")

    # Gunicorn configuration
    gunicorn_config = [
        "inmemory.api.deploy:create_production_app",
        "--workers",
        str(config["workers"]),
        "--worker-class",
        "uvicorn.workers.UvicornWorker",
        "--bind",
        f"{config['host']}:{config['port']}",
        "--log-level",
        config["log_level"].lower(),
        "--access-logfile",
        "-",
        "--error-logfile",
        "-",
    ]

    # Add log file if specified
    if config["log_file"]:
        gunicorn_config.extend(["--access-logfile", config["log_file"]])

    # Run gunicorn
    sys.argv = ["gunicorn"] + gunicorn_config
    wsgi.run()


def run_docker_server():
    """Run the API server optimized for Docker containers."""
    config = load_environment_config()

    # Docker-specific defaults
    config["host"] = "0.0.0.0"  # Bind to all interfaces in container
    config["workers"] = max(1, (os.cpu_count() or 1))  # Use all CPU cores

    setup_logging(config["log_level"])

    logging.info("Starting InMemory API server for Docker")
    logging.info(f"Using {config['workers']} workers")

    app = create_production_app()

    uvicorn.run(
        app,
        host=config["host"],
        port=config["port"],
        workers=config["workers"],
        log_level=config["log_level"].lower(),
        access_log=True,
    )


def print_deployment_info():
    """Print deployment information and environment variables."""
    print("InMemory API Server Deployment Configuration")
    print("=" * 50)

    config = load_environment_config()

    print(f"Host: {config['host']}")
    print(f"Port: {config['port']}")
    print(f"Workers: {config['workers']}")
    print(f"Log Level: {config['log_level']}")
    print(f"Storage Type: {config['storage_type']}")
    print(f"Docs Enabled: {config['enable_docs']}")
    print(f"CORS Origins: {config['cors_origins']}")

    print("\nEnvironment Variables:")
    print("-" * 30)
    env_vars = [
        "INMEMORY_HOST",
        "INMEMORY_PORT",
        "INMEMORY_WORKERS",
        "INMEMORY_LOG_LEVEL",
        "INMEMORY_STORAGE_TYPE",
        "INMEMORY_MONGODB_URI",
        "INMEMORY_CORS_ORIGINS",
    ]

    for var in env_vars:
        value = os.getenv(var, "not set")
        # Hide sensitive values
        if "URI" in var or "KEY" in var or "SECRET" in var:
            value = "***" if value != "not set" else "not set"
        print(f"{var}: {value}")


def main():
    """Main entry point for deployment commands."""
    if len(sys.argv) < 2:
        print("Usage: python -m inmemory.api.deploy <command>")
        print("Commands:")
        print("  dev         - Run development server")
        print("  prod        - Run production server with Gunicorn")
        print("  docker      - Run server optimized for Docker")
        print("  info        - Show deployment configuration")
        sys.exit(1)

    command = sys.argv[1]

    if command == "dev":
        run_development_server()
    elif command == "prod":
        run_production_server()
    elif command == "docker":
        run_docker_server()
    elif command == "info":
        print_deployment_info()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
