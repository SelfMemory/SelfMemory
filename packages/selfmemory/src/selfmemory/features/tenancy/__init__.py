"""Organizations, projects, members, invitations and the scope access gate."""

from selfmemory.kernel.feature import AppContext, Feature


def register(ctx: AppContext) -> None:
    from selfmemory.features.tenancy.interfaces.http import (
        invitations,
        notifications,
        organizations,
        projects,
        users,
    )

    for module in (organizations, projects, invitations, users, notifications):
        ctx.add_router(module.router)


FEATURE = Feature(name="tenancy", register=register)
