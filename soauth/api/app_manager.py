"""
Endpoints for managing Apps created in the identity system.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from soauth.core.app import AppData
from soauth.core.models import AppDetailResponse, AppRefreshResponse
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

app_management_routes = APIRouter(tags=["App Management"])


class AppCreationRequest(BaseModel):
    name: str
    domain: str
    redirect_url: str
    visibility_grant: str | None = None
    api_access: bool = False


@app_management_routes.put(
    "/app",
    summary="Create a new application",
    description=(
        "Create a new application with a specified domain and redirect URL.\n\n"
        "The user must have the appropriate grants (`admin` or `appmanager`) to perform this action."
    ),
    responses={
        200: {"description": "The application's details and keys are returned."},
        401: {"description": "Unauthorized to manage this application."},
    },
)
async def create_app(
    model: AppCreationRequest,
    user: AppManagerUser,
    conn: DatabaseDependency,
    settings: SettingsDependency,
    log: LoggerDependency,
) -> AppRefreshResponse:
    log = log.bind(user=user, creation_request=model)
    # Note: the 'user' as given by the auth system is not the same as our database
    # user, it's re-created from the webtoken.
    database_user = await user_service.read_by_id(user_id=user.user_id, conn=conn)
    app = await app_service.create(
        name=model.name,
        domain=model.domain,
        redirect_url=model.redirect_url,
        visibility_grant=model.visibility_grant,
        api_access=model.api_access,
        user=database_user,
        settings=settings,
        conn=conn,
        log=log,
    )
    log = log.bind(app_id=app.app_id)
    await log.ainfo("api.appmanager.app.created")

    return AppRefreshResponse(
        app=app.to_core(),
        public_key=app.public_key.decode("utf-8"),
        key_pair_type=app.key_pair_type,
        client_secret=app.client_secret,
    )


@app_management_routes.get(
    "/apps",
    summary="Get the list of applications",
    description=(
        "Retrieve a list of applications created by the user (if `appmanager`) or all applications "
        "(if `admin`)."
    ),
    responses={
        200: {"description": "A list of applications is returned."},
        401: {"description": "Unauthorized to manage applications."},
    },
)
async def apps(
    user: AppManagerUser, conn: DatabaseDependency, log: LoggerDependency
) -> list[AppData]:
    log = log.bind(user=user)
    created_by = None if "admin" in user.grants else user.user_id
    database_user = await user_service.read_by_id(user_id=user.user_id, conn=conn)
    result = await app_service.get_app_list(
        created_by_user_id=created_by, user=database_user, conn=conn
    )
    log.bind(number_of_apps=len(result))
    await log.ainfo("api.appmanager.apps")
    return result


@app_management_routes.get(
    "/app/{app_id}",
    summary="Get application details",
    description=(
        "Retrieve detailed information about an application, including its internal properties "
        "and a list of logged-in users. Requires the user to be the app's manager or an admin."
    ),
    responses={
        200: {"description": "Application details are returned."},
        401: {"description": "Unauthorized to access this application."},
    },
)
async def app(
    app_id: UUID, user: AppManagerUser, conn: DatabaseDependency, log: LoggerDependency
) -> AppDetailResponse:
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
    return AppDetailResponse(app=result.to_core(), users=logged_in_users)


@app_management_routes.post(
    "/app/{app_id}/refresh",
    summary="Refresh application keys",
    description=(
        "Refresh the keys and client secret for an application. The old keys are immediately expired. "
        "Requires `appmanager` or `admin` grants."
    ),
    responses={
        200: {"description": "New keys and client secret are returned."},
        401: {"description": "Unauthorized to refresh this application."},
    },
)
async def refresh(
    app_id: UUID,
    user: AppManagerUser,
    conn: DatabaseDependency,
    settings: SettingsDependency,
    log: LoggerDependency,
) -> AppRefreshResponse:
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

    return AppRefreshResponse(
        app=app.to_core(),
        public_key=app.public_key.decode("utf-8"),
        key_pair_type=app.key_pair_type,
        client_secret=app.client_secret,
    )


@app_management_routes.delete(
    "/app/{app_id}",
    summary="Delete an application",
    description=(
        "Delete an application permanently. This action also removes all associated refresh keys, "
        "making them invalid. Requires `appmanager` or `admin` grants."
    ),
    responses={
        200: {"description": "Application deleted successfully."},
        401: {"description": "Unauthorized to delete this application."},
    },
)
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
