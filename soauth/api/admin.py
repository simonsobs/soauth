"""
Administration endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from soauth.core.app import LoggedInUserData
from soauth.core.uuid import UUID
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

admin_app = APIRouter()


@admin_app.get("/users")
async def users(
    admin_user: AdminUser, conn: DatabaseDependency, log: LoggerDependency
) -> list[user_service.UserData]:
    log = log.bind(admin_user=admin_user)
    result = await user_service.get_user_list(conn=conn)
    log = log.bind(number_of_users=len(result))
    await log.ainfo("api.admin.users")
    return result


@admin_app.get("/user/{user_id}")
async def user(
    user_id: UUID,
    admin_user: AdminUser,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> dict[str, user_service.UserData | list[LoggedInUserData]]:
    log = log.bind(admin_user=admin_user, requested_user_id=user_id)
    result = (await user_service.read_by_id(user_id=user_id, conn=conn)).to_core()
    login_details = await refresh_service.get_all_logins_for_user(
        user_id=user_id, conn=conn, log=log
    )
    log = log.bind(read_user=result)
    await log.ainfo("api.admin.user")
    return {"user": result, "logins": login_details}


class ModifyUserContent(BaseModel):
    grant_add: str | None = None
    grant_remove: str | None = None


@admin_app.post("/user/{user_id}")
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


@admin_app.post("/user/{user_id}/revoke")
async def revoke(user_id: UUID, admin_user: AdminUser) -> user_service.UserData:
    """
    Revoke all of a user's access keys and refresh their user.
    """

    # TODO: Implement refresh_user stuff.
    return None


@admin_app.delete("/user/{user_id}")
async def delete(
    user_id: UUID,
    admin_user: AdminUser,
    conn: DatabaseDependency,
    log: LoggerDependency,
):
    """
    Delete a user!
    """
    log = log.bind(admin_user=admin_user, requested_user_id=user_id)
    user = await user_service.read_by_id(user_id=user_id, conn=conn)
    log = log.bind(user=user)
    await user_service.delete(user_name=user.user_name, conn=conn, log=log)
    await log.ainfo("api.admin.user_deleted")


@admin_app.delete("/keys/{key_id}")
async def revoke_key(
    key_id: UUID,
    admin_user: AdminUser,
    conn: DatabaseDependency,
    log: LoggerDependency,
):
    """
    Revoke a key!
    """
    log = log.bind(admin_user=admin_user, requested_key_id=key_id)
    await refresh_service.expire_refresh_key_by_id(key_id=key_id, conn=conn)
    await log.ainfo("api.admin.key_revoked")
    return
