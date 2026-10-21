"""Local development stack for SelfMemory.

Brings up everything the API needs, in the order it needs it, and proves each
piece is ready before moving on.

Commands:
    up       start Mongo and the API (with its run worker); block until Ctrl-C
    down     stop the containers (volumes kept)
    status   report what is currently running
    check    run preflight only, change nothing

Configuration comes from ``.env`` and the environment; see ``settings.py``.
Run ``make help`` for the Makefile wrappers.
"""

from __future__ import annotations

from scripts.devstack.lifecycle import PreflightError, down, status, up
from scripts.devstack.settings import ConfigError, Settings, load_settings
from scripts.devstack.waiters import ProbeError

# The readiness probes raise the builtin TimeoutError rather than a wrapper, so
# callers can catch it without importing anything from this package.
__all__ = [
    "ConfigError",
    "PreflightError",
    "ProbeError",
    "Settings",
    "down",
    "load_settings",
    "status",
    "up",
]
