import importlib.metadata

__version__ = importlib.metadata.version("selfmemory")

from selfmemory.memory.main import SelfMemory  # noqa
from selfmemory.client.main import SelfMemoryClient  # noqa
