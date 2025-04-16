"""
Endpoints for managing Apps created in the identity system.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from soauth.core.app import AppData, LoggedInUserData
from soauth.core.uuid import UUID
from soauth.service import app as app_service
from soauth.service import refresh as refresh_service
from soauth.service import user as user_service
from soauth.toolkit.fastapi import SOUserWithGrants, handle_authenticated_user

from .dependencies import DatabaseDependency, LoggerDependency, SettingsDependency

CANNOT_MANAGE_THIS_APP = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="You cannot manage this application",
)


async def handle_app_manager_user(request: Request) -> SOUserWithGrants:
    user = await handle_authenticated_user(request=request)

    if "admin" in user.grants or "appmanager" in user.grants:
        return user

    raise CANNOT_MANAGE_THIS_APP


AppManagerUser = Annotated[SOUserWithGrants, Depends(handle_app_manager_user)]

app_manager_app = APIRouter()


@app_manager_app.put("/app")
async def create_app(
    domain: str,
    redirect_url: str,
    user: AppManagerUser,
    conn: DatabaseDependency,
    settings: SettingsDependency,
    log: LoggerDependency,
) -> dict[str, AppData | str]:
    log = log.bind(user=user, domain=domain)
    # Need to get the 'user' from the 'user'
    database_user = await user_service.read_by_id(user_id=user.user_id, conn=conn)
    app = await app_service.create(
        domain=domain,
        redirect_url=redirect_url,
        user=database_user,
        settings=settings,
        conn=conn,
        log=log,
    )
    log = log.bind(app_id=app.app_id)
    await log.ainfo("api.appmanager.app.created")
    return {
        "app": app.to_core(),
        "public_key": app.public_key.decode("utf-8"),
        "key_pair_type": app.key_pair_type,
        "client_secret": app.client_secret,
    }


@app_manager_app.get("/apps")
async def apps(
    user: AppManagerUser, conn: DatabaseDependency, log: LoggerDependency
) -> list[AppData]:
    log = log.bind(user=user)
    created_by = None if "admin" in user.grants else user.user_id
    result = await app_service.get_app_list(created_by, conn=conn)
    log.bind(number_of_apps=len(result))
    await log.ainfo("api.appmanager.apps")
    return result


@app_manager_app.get("/app/{app_id}")
async def app(
    app_id: UUID, user: AppManagerUser, conn: DatabaseDependency, log: LoggerDependency
) -> dict[str, AppData | list[LoggedInUserData]]:
    log = log.bind(user=user, requested_app_id=app_id)
    result = await app_service.read_by_id(app_id=app_id, conn=conn)
    log.bind(created_by_user_id=result.created_by_user_id)

    if (result.created_by_user_id != user.user_id) and ("admin" not in user.grants):
        await log.ainfo("api.appmanager.app.request_failed")
        raise CANNOT_MANAGE_THIS_APP

    logged_in_users = await refresh_service.get_logged_in_users(
        app_id=app_id, conn=conn, log=log
    )

    await log.ainfo("api.appmanager.app")
    return {"app": result.to_core(), "users": logged_in_users}


@app_manager_app.post("/app/{app_id}/refresh")
async def refresh(
    app_id: UUID,
    user: AppManagerUser,
    conn: DatabaseDependency,
    settings: SettingsDependency,
    log: LoggerDependency,
) -> dict[str, AppData | str]:
    log = log.bind(user=user, requested_app_id=app_id)
    result = await app_service.read_by_id(app_id=app_id, conn=conn)
    log.bind(created_by_user_id=result.created_by_user_id)

    if (result.created_by_user_id != user.user_id) and ("admin" not in user.grants):
        await log.ainfo("api.appmanager.refresh.request_failed")
        raise CANNOT_MANAGE_THIS_APP

    app = await app_service.refresh_keys(
        app_id=app_id, settings=settings, conn=conn, log=log
    )
    await log.ainfo("api.appmanager.refresh.success")

    return {
        "app": app.to_core(),
        "client_secret": app.client_secret,
        "public_key": app.public_key.decode("utf-8"),
        "key_pair_type": app.key_pair_type,
    }


@app_manager_app.delete("/app/{app_id}")
async def delete(
    app_id: UUID,
    user: AppManagerUser,
    conn: DatabaseDependency,
    settings: SettingsDependency,
    log: LoggerDependency,
):
    log = log.bind(user=user, requested_app_id=app_id)
    result = await app_service.read_by_id(app_id=app_id, conn=conn)
    log.bind(created_by_user_id=result.created_by_user_id)

    if (result.created_by_user_id != user.user_id) and ("admin" not in user.grants):
        await log.ainfo("api.appmanager.delete.request_failed")
        raise CANNOT_MANAGE_THIS_APP

    await app_service.delete(app_id=app_id, conn=conn, log=log)
    await log.ainfo("api.appmanager.delete.success")
