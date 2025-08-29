import importlib.metadata

__version__ = importlib.metadata.version("inmemory")

from inmemory.client import InmemoryClient  # noqa
from inmemory.memory.main import Memory  # noqa
