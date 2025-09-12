"""
Utils module for embedding generation and utility functions.

Contains embedding utilities and helper functions.
"""

# Conditional imports for backward compatibility
try:
    from .embeddings import generate_embeddings, get_embeddings

    _EMBEDDINGS_AVAILABLE = True
except ImportError:
    generate_embeddings = None
    get_embeddings = None
    _EMBEDDINGS_AVAILABLE = False

__all__ = []

# Add embeddings exports if available
if _EMBEDDINGS_AVAILABLE:
    __all__.extend(
        [
            "get_embeddings",
            "generate_embeddings",
        ]
    )
