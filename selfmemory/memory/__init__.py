"""
Memory module for SelfMemory SDK.

This module provides the main Memory class and related functionality
for local memory management with zero-setup requirements.
"""

from selfmemory.memory.base import MemoryBase
from selfmemory.memory.main import Memory

__all__ = ["Memory", "MemoryBase"]
