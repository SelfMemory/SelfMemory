"""Capabilities, one vertical slice per folder.

``BUILTIN`` is the explicit registry ``apps/api.py`` mounts; plugins add more
through the ``selfmemory.features`` entry-point group.
"""

from selfmemory.features.a2a import FEATURE as A2A
from selfmemory.features.api_keys import FEATURE as API_KEYS
from selfmemory.features.tenancy import FEATURE as TENANCY
from selfmemory.features.wiki import FEATURE as WIKI

BUILTIN = [TENANCY, API_KEYS, WIKI, A2A]
