"""
API endpoints for API key management.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request, status

from soauth.api.dependencies import DatabaseDependency, SettingsDependency
from soauth.app.dependencies import LoggerDependency
from soauth.core.models import APIKeyCreationResponse, AppDetailResponse
from soauth.service import app as app_service
from soauth.service import refresh as refresh_service
from soauth.service import user as user_service
from soauth.toolkit.fastapi import AuthenticatedUserDependency

key_management_routes = APIRouter(tags=["API Key Management"])


@key_management_routes.get(
    "/app/{app_id}",
    summary="Get a new API key for a given app.",
    description=(
        "Request a new API key (actually a refresh token that their "
        "client will exchange for a novel access token)."
    ),
    responses={
        200: {"description": "Tokens successfully returned"},
        401: {"description": "Authentication failed"},
        404: {"description": "App not found"},
        500: {"description": "Internal server error"},
    },
)
async def create(
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
    user: AuthenticatedUserDependency,
    app_id: UUID = Path(..., description="The app ID to generate keys for."),
) -> APIKeyCreationResponse:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
    )

    try:
        database_user = await user_service.read_by_id(user_id=user.user_id, conn=conn)
    except user_service.UserNotFound:
        raise unauthorized

    try:
        app = await app_service.read_by_id(app_id=app_id, conn=conn)
    except app_service.AppNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="App not found"
        )

    content, key = await refresh_service.create_refresh_key(
        user=database_user, app=app, api_key=True, settings=settings, conn=conn
    )

    return APIKeyCreationResponse(
        app_id=app.app_id,
        app_name=app.app_name,
        app_hostname=app.domain,
        refresh_token=content,
        refresh_token_expires=key.expires_at,
    )


@key_management_routes.get(
    "/list",
    summary="Get the list of apps that can be authenticated against.",
    description=(
        "Returns the list of all applications (those that have api_access=True in their "
        "configuration and hence allow for the creation of API keys). Includes information "
        "about the current user's active sessions within those apps"
    ),
)
async def list(
    request: Request,
    conn: DatabaseDependency,
    log: LoggerDependency,
    user: AuthenticatedUserDependency,
) -> list[AppDetailResponse]:
    # In theory we can chain these futures, but not worth it.
    database_user = await user_service.read_by_id(user_id=user.user_id, conn=conn)

    log = log.bind(user_id=database_user.user_id, user_name=database_user.user_name)

    app_list = await app_service.get_app_list(
        created_by_user_id=None, user=database_user, conn=conn, require_api_access=False
    )

    log = log.bind(
        number_of_apps=len(app_list),
        app_list=[x.app_name for x in app_list],
    )

    login_list = await refresh_service.get_all_logins_for_user(
        user_id=user.user_id, conn=conn, log=log
    )

    log = log.bind(
        number_of_logins=len(login_list),
        login_list=[f"{y.app_id} ({y.app_name})" for y in login_list],
    )

    await log.ainfo("api.key_management.list")

    return [
        AppDetailResponse(app=x, users=[y for y in login_list if y.app_id == x.app_id])
        for x in app_list
    ]
