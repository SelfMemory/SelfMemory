"""Feature registry: how a capability plugs itself into the processes.

Each folder under ``selfmemory.features`` exposes ``FEATURE = Feature(...)``.
``apps/api.py`` walks the registry (the built-in list plus any third-party
package registered under the ``selfmemory.features`` entry-point group) and
calls ``register`` with an :class:`AppContext`, so a new feature's routers
appear without editing a central file.
"""

from __future__ import annotations

from collections.abc import Callable  # noqa: TC003 - used at runtime by dataclass
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any, Protocol

ENTRY_POINT_GROUP = "selfmemory.features"


class AppContext(Protocol):
    """What a feature may touch while registering. Implemented by the app."""

    def add_router(self, router: Any) -> None:
        """Mount an HTTP router under the versioned API prefix."""
        ...

    def add_public_router(self, router: Any) -> None:
        """Mount a router at the site root, for well-known discovery paths."""
        ...


@dataclass(frozen=True)
class Feature:
    name: str
    register: Callable[[AppContext], None]


def discover(builtin: list[Feature]) -> list[Feature]:
    """The built-in features followed by any installed plugin features."""
    features = list(builtin)
    seen = {f.name for f in features}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        feature = ep.load()
        if not isinstance(feature, Feature):
            raise TypeError(f"entry point {ep.name!r} is not a Feature")
        if feature.name in seen:
            raise ValueError(f"duplicate feature {feature.name!r}")
        seen.add(feature.name)
        features.append(feature)
    return features
