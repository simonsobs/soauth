"""
Administration endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from soauth.core.uuid import UUID
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
) -> user_service.UserData:
    log = log.bind(admin_user=admin_user, requested_user_id=user_id)
    result = (await user_service.read_by_id(user_id=user_id, conn=conn)).to_core()
    log = log.bind(read_user=result)
    await log.ainfo("api.admin.user")
    return result


@admin_app.post("/user/{user_id}")
async def modify_user(user_id: UUID, admin_user: AdminUser) -> user_service.UserData:
    return None


@admin_app.post("/user/{user_id}/revoke")
async def revoke(user_id: UUID, admin_user: AdminUser) -> user_service.UserData:
    """
    Revoke all of a user's access keys and refresh their user.
    """

    # TODO: Implement refresh_user stuff.
    return None


@admin_app.delete("/user/{user_id}")
async def delete(user_id: UUID, admin_user: AdminUser):
    """
    Delete a user!
    """

    return
