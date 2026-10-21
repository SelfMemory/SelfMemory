"""The wiki engine: scoped OKF knowledge bundles maintained by an agent.

Raw sources are uploaded into a scope's ``raw/`` directory, an opencode agent
running inside a verified sandbox files them into that scope's ``wiki/`` (one
git repository per scope), and questions are answered by the same agent,
read-only, with citations to the pages it read.

``domain`` holds the pure scope rules, ``adapters`` the filesystem, git,
graph and search code, ``service`` the use cases and ``interfaces`` the HTTP
router and MCP tools. Runs live in ``features.runs``, authorization in
``features.tenancy.access``.
"""

from selfmemory.features.wiki.domain.layout import ORG_KEY, Scope
from selfmemory.kernel.feature import AppContext, Feature
from selfmemory.kernel.safe_paths import PathRefused
from selfmemory.wiki_settings import WikiSettings, load_settings


def register(ctx: AppContext) -> None:
    from selfmemory.features.wiki.interfaces.http import router

    ctx.add_router(router)


FEATURE = Feature(name="wiki", register=register)

__all__ = [
    "FEATURE",
    "ORG_KEY",
    "PathRefused",
    "Scope",
    "WikiSettings",
    "load_settings",
]
