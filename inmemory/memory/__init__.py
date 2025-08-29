"""
Memory module for InMemory SDK.

This module provides the main Memory class and related functionality
for local memory management with zero-setup requirements.
"""

from inmemory.memory.main import Memory
from inmemory.memory.base import MemoryBase

__all__ = ["Memory", "MemoryBase"]
