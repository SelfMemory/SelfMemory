"""Project-scoped API keys."""

from selfmemory.kernel.feature import AppContext, Feature


def register(ctx: AppContext) -> None:
    from selfmemory.features.api_keys.interfaces.http import router

    ctx.add_router(router)


FEATURE = Feature(name="api_keys", register=register)
