"""Agent-to-agent access to the wiki (the A2A protocol, JSON-RPC binding).

Another agent -- typically a user's coding agent asking on their behalf --
sends a message and gets a task back. The mapping onto the wiki:

    A2A contextId  ->  a chat of kind "a2a" (one opencode session)
    A2A task       ->  one query run (job); its id is the job id

A message without a ``contextId`` starts a new context, so nothing carries
over. Tasks of one context run one at a time in arrival order; tasks of
different contexts run in parallel up to the caller's fair-share cap. A task
keeps running when the caller disconnects, and its result stays readable for
``run_retention_s``; an idle context is deleted after ``context_idle_ttl_s``.
"""

from selfmemory.kernel.feature import AppContext, Feature


def register(ctx: AppContext) -> None:
    from selfmemory.features.a2a.interfaces.http import card_router, router

    ctx.add_router(router)
    ctx.add_public_router(card_router)


FEATURE = Feature(name="a2a", register=register)

__all__ = ["FEATURE"]
