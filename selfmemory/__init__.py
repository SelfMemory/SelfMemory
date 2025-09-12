import importlib.metadata

__version__ = importlib.metadata.version("selfmemory")

from selfmemory.client import SelfMemoryClient  # noqa
from selfmemory.memory.main import Memory  # noqa
