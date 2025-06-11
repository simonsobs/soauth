"""
Administration endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from soauth.core.group import GroupData
from soauth.core.models import (
    ModifyGroupContent,
    ModifyUserContent,
    UserDetailResponse,
)
from soauth.core.uuid import UUID
from soauth.service import groups as group_service
from soauth.service import refresh as refresh_service
from soauth.service import user as user_service
from soauth.toolkit.fastapi import SOUserWithGrants, handle_authenticated_user

from .dependencies import DatabaseDependency, LoggerDependency


async def handle_admin_user(request: Request) -> SOUserWithGrants:
    user = await handle_authenticated_user(request=request)

    if "admin" not in user.grants:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This endpoint requires the 'admin' grant",
        )

    return user


AdminUser = Annotated[SOUserWithGrants, Depends(handle_admin_user)]

admin_routes = APIRouter(tags=["Administration"])


@admin_routes.get(
    "/users",
    summary="Get the list of users",
    description="Retrieve a list of all users in the system. Requires `admin` grant.",
    responses={
        200: {"description": "A list of users is returned."},
        401: {"description": "Unauthorized to access this endpoint."},
    },
)
async def users(
    admin_user: AdminUser, conn: DatabaseDependency, log: LoggerDependency
) -> list[user_service.UserData]:
    log = log.bind(admin_user=admin_user)
    result = await user_service.get_user_list(conn=conn)
    log = log.bind(number_of_users=len(result))
    await log.ainfo("api.admin.users")
    return result


@admin_routes.get(
    "/user/{user_id}",
    summary="Get user details",
    description=(
        "Retrieve detailed information about a user, including their currently active sessions. "
        "Requires `admin` grant."
    ),
    responses={
        200: {"description": "User details and active sessions are returned."},
        401: {"description": "Unauthorized to access this endpoint."},
    },
)
async def user(
    user_id: UUID,
    admin_user: AdminUser,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> UserDetailResponse:
    log = log.bind(admin_user=admin_user, requested_user_id=user_id)
    result = (await user_service.read_by_id(user_id=user_id, conn=conn)).to_core()
    login_details = await refresh_service.get_all_logins_for_user(
        user_id=user_id, conn=conn, log=log
    )
    log = log.bind(read_user=result)
    await log.ainfo("api.admin.user")
    return UserDetailResponse(user=result, logins=login_details)


@admin_routes.post(
    "/user/{user_id}",
    summary="Modify user grants",
    description=(
        "Add or remove grants for a user. Requires `admin` grant. "
        "Specify the grant to add or remove in the request body."
    ),
    responses={
        200: {"description": "User grants modified successfully."},
        401: {"description": "Unauthorized to access this endpoint."},
    },
)
async def modify_user(
    content: ModifyUserContent,
    user_id: UUID,
    admin_user: AdminUser,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> user_service.UserData:
    log = log.bind(admin_user=admin_user, requested_user_id=user_id)

    user = await user_service.read_by_id(user_id=user_id, conn=conn)

    if (grant := content.grant_add) is not None:
        await user_service.add_grant(
            user_name=user.user_name, grant=grant, conn=conn, log=log
        )
        log = log.bind(added_grant=grant)

    if (grant := content.grant_remove) is not None:
        await user_service.remove_grant(
            user_name=user.user_name, grant=grant, conn=conn, log=log
        )
        log = log.bind(removed_grant=grant)

    await log.ainfo("api.admin.modify_user")

    return user.to_core()


@admin_routes.post(
    "/user/{user_id}/revoke",
    summary="Revoke all user access keys",
    description=(
        "Revoke all access keys for a user and refresh their user data. "
        "Requires `admin` grant."
    ),
    responses={
        200: {"description": "User access keys revoked successfully."},
        401: {"description": "Unauthorized to access this endpoint."},
    },
    include_in_schema=False,  # NOT IMPLEMENTED, DO NOT INCLUDE
)
async def revoke(user_id: UUID, admin_user: AdminUser) -> user_service.UserData:
    """
    Revoke all of a user's access keys and refresh their user.
    """

    # TODO: Implement refresh_user stuff.
    return None


@admin_routes.delete(
    "/user/{user_id}",
    summary="Delete a user",
    description=("Permanently delete a user from the system. Requires `admin` grant."),
    responses={
        200: {"description": "User deleted successfully."},
        401: {"description": "Unauthorized to access this endpoint."},
    },
)
async def delete(
    user_id: UUID,
    admin_user: AdminUser,
    conn: DatabaseDependency,
    log: LoggerDependency,
):
    log = log.bind(admin_user=admin_user, requested_user_id=user_id)
    user = await user_service.read_by_id(user_id=user_id, conn=conn)
    log = log.bind(user=user)
    await user_service.delete(user_name=user.user_name, conn=conn, log=log)
    await log.ainfo("api.admin.user_deleted")


@admin_routes.delete(
    "/keys/{key_id}",
    summary="Revoke a refresh key",
    description=(
        "Revoke a specific refresh key, effectively invalidating it. "
        "Requires `admin` grant."
    ),
    responses={
        200: {"description": "Refresh key revoked successfully."},
        401: {"description": "Unauthorized to access this endpoint."},
    },
)
async def revoke_key(
    key_id: UUID,
    admin_user: AdminUser,
    conn: DatabaseDependency,
    log: LoggerDependency,
):
    log = log.bind(admin_user=admin_user, requested_key_id=key_id)
    await refresh_service.expire_refresh_key_by_id(key_id=key_id, conn=conn)
    await log.ainfo("api.admin.key_revoked")
    return


@admin_routes.post(
    "/group/{group_id}",
    summary="Modify group grants",
    description=(
        "Add or remove grants for a group. All members of the group will "
        "inherit these grants. Requires `admin` grant."
    ),
    responses={
        200: {"description": "Group grants modified successfully."},
        401: {"description": "Unauthorized to access this endpoint."},
    },
)
async def modify_group(
    content: ModifyGroupContent,
    group_id: UUID,
    admin_user: AdminUser,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> GroupData:
    log = log.bind(admin_user=admin_user, requested_group_id=group_id)

    group = await group_service.read_by_id(group_id=group_id, conn=conn, log=log)

    if grant := content.grant_add:
        await group_service.add_grant(
            group_name=group.group_name, grant=grant, conn=conn, log=log
        )
        log = log.bind(added_grant=grant)

    if grant := content.grant_remove:
        await group_service.remove_grant(
            group_name=group.group_name, grant=grant, conn=conn, log=log
        )
        log = log.bind(removed_grant=grant)

    await log.ainfo("api.admin.modify_group")

    return group.to_core()
