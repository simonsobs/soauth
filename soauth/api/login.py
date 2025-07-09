"""
Main login flow - redirection to GitHub and handling of responses.
"""

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from fastapi.responses import RedirectResponse

from soauth.core.models import KeyRefreshResponse, RefreshTokenModel
from soauth.core.tokens import KeyExpiredError
from soauth.core.uuid import UUID
from soauth.service import app as app_service
from soauth.service import flow as flow_service
from soauth.service import login as login_service
from soauth.service import provider as provider_service
from soauth.service import refresh as refresh_service
from soauth.service import user as user_service
from soauth.toolkit.fastapi import AuthenticatedUserDependency

from .dependencies import (
    SETTINGS,
    AuthProviderDependency,
    DatabaseDependency,
    LoggerDependency,
    SettingsDependency,
)

login_app = APIRouter(tags=["Login and Session Management"])


@login_app.get(
    "/login/{app_id}",
    response_class=RedirectResponse,
    summary="Redirect user to GitHub for login",
    description=(
        "Login flow - use this endpoint to initiate GitHub login and validate the session.\n\n"
        "The user will be redirected either to the main page of your registered app, or (preferentially) "
        "to the URL defined in the `Referer` header.\n\n"
        "If the redirection does not work as expected, consider setting "
        '`referrerpolicy="no-referrer-when-downgrade"` in your client.'
    ),
    responses={
        302: {"description": "Redirect to GitHub login"},
        404: {"description": "App not found"},
    },
)
async def login(
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
    provider: AuthProviderDependency,
    app_id: UUID = Path(..., description="The app ID to authenticate against."),
    next: str | None = Query(
        None,
        description=(
            "Optional path to redirect to after login. If not provided, the user will be redirected "
            "to the app's main page or the `Referer` header."
        ),
    ),
) -> RedirectResponse:
    try:
        app = await app_service.read_by_id(app_id=app_id, conn=conn)
    except app_service.AppNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"App {app_id} not found")

    if next is not None:
        redirect_to = f"{app.domain}/{next}"
    elif request.headers.get("Referer", None) is not None:
        redirect_to = request.headers["Referer"]
    else:
        redirect_to = None

    log = log.bind(redirect_to_after_login=redirect_to, app_id=app_id)

    login_request = await login_service.create(
        app=app, redirect_to=redirect_to, conn=conn, log=log
    )

    redirect_url = await provider.redirect(
        login_request=login_request, settings=settings
    )

    log = log.bind(
        redirect_url=redirect_url, login_request_id=login_request.login_request_id
    )
    await log.ainfo("api.login.login.redirect")

    return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)


@login_app.get(
    "/github",
    response_class=RedirectResponse,
    summary="Handle GitHub OAuth callback",
    description=(
        "This endpoint is called by GitHub as part of the OAuth login flow. "
        "It completes the login by exchanging the `code` for user credentials and redirects "
        "the user to the app's final redirect URL based on the login request.\n\n"
        "This should not be called directly by users—GitHub calls this after the user authorizes "
        "the application."
    ),
    responses={
        302: {"description": "Redirect to the final app URL"},
        401: {"description": "Authentication failed"},
    },
)
async def github(
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
    provider: AuthProviderDependency,
    code: str = Query(
        ..., description="The code to exchange for GitHub auth credentials."
    ),
    state: UUID = Query(..., description="Login request ID used to identify the user."),
) -> RedirectResponse:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
    )

    log = log.bind(login_request_id=state)

    # Check that this login request is valid on our end, by reconstructing our
    # login request from the database.
    try:
        login_request = await login_service.read(login_request_id=state, conn=conn)
    except login_service.StaleRequestError:
        await log.aerror("api.login.github.stale")
        raise unauthorized

    # This calls GitHub upp and authenticates as the user, allowing us access
    # to user information and to actually validate the login
    try:
        user = await provider.login(code=code, settings=settings, conn=conn, log=log)
        login_request.user_id = user.user_id
        conn.add(user)
    except provider_service.BaseLoginError:
        await log.aerror("api.login.github.github_error")
        raise unauthorized

    await log.ainfo("api.login.github.success")

    app = await app_service.read_by_id(app_id=login_request.app_id, conn=conn)

    # Limit the length of external strings sent downstream.
    response = RedirectResponse(
        url=f"{app.redirect_url}?code={login_request.secret_code}&state={str(state)[:256]}",
        status_code=302,
    )

    return response


@login_app.post(
    "/code/{app_id}",
    response_model=KeyRefreshResponse,
    summary="Exchange a code and client secret for tokens",
    description=(
        "Exchange an authorization `code` and a client `secret` for an access token, "
        "refresh token, token expiry times, and a redirect URL.\n\n"
        "The redirect URL is where the user should be sent after the exchange is complete. "
        "This will be either the root of your app or the original URL the user came from."
    ),
    responses={
        200: {"description": "Tokens successfully returned"},
        401: {"description": "Authentication failed"},
    },
)
async def code(
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
    code: str = Query(
        ..., description="The access code you received at your `/callback` endpoint."
    ),
    secret: str = Query(
        ..., description="The client secret provided during app initialization."
    ),
    app_id: UUID = Path(
        ..., description="The app ID provided during app initialization."
    ),
) -> KeyRefreshResponse:
    # All of this can be surely balled up into a service layer function?

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
    )

    try:
        login_request = await login_service.read_by_code(
            code=code, secret=secret, conn=conn
        )
    except login_service.StaleRequestError as e:
        log = log.bind(error=e)
        await log.ainfo("api.login.code.read_failed")
        raise unauthorized

    try:
        user = await user_service.read_by_id(user_id=login_request.user_id, conn=conn)
    except user_service.UserNotFound as e:
        log = log.bind(error=e)
        await log.ainfo("api.login.code.user_failed")
        raise unauthorized

    if app_id != login_request.app_id:
        log = log.bind(
            requested_app_id=app_id,
            recovered_app_id=login_request.app_id,
        )
        await log.ainfo("api.login.code.app_failed")

    # Create the codes!
    app = await app_service.read_by_id(app_id=login_request.app_id, conn=conn)
    key_content = await flow_service.primary(
        user=user, app=app, settings=settings, conn=conn, log=log
    )

    # Check in to make sure we're still valid and close out the login
    try:
        redirect = await login_service.complete(
            login_request=login_request, user=user, conn=conn, log=log
        )
    except (login_service.StaleRequestError, login_service.RedirectInvalidError) as e:
        log = log.bind(error=e)
        await log.aerror("api.login.code.redirect_error")
        raise unauthorized

    log = log.bind(
        redirect_to=redirect, login_request_id=login_request.login_request_id
    )

    return KeyRefreshResponse(
        access_token=key_content.access_token,
        refresh_token=key_content.refresh_token,
        profile_data=key_content.profile_data,
        access_token_expires=key_content.access_token_expires,
        refresh_token_expires=key_content.refresh_token_expires,
        redirect=redirect,
    )


@login_app.post(
    "/exchange",
    response_model=KeyRefreshResponse,
    summary="Exchange a refresh token for new tokens",
    description=(
        "Exchange a valid refresh token for a new access token and a new refresh token. "
        "The old refresh token becomes invalid after this call.\n\n"
        "You must provide the `refresh_token` in the request body."
    ),
    responses={
        200: {"description": "New access and refresh tokens returned"},
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def exchange(
    content: RefreshTokenModel,
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
    provider: AuthProviderDependency,
) -> KeyRefreshResponse:
    refresh_token = content.refresh_token

    try:
        key_content = await flow_service.secondary(
            encoded_refresh_key=refresh_token,
            settings=settings,
            conn=conn,
            log=log,
            provider=provider,
        )
    except refresh_service.AuthorizationError as e:
        log = log.bind(error=str(e))
        await log.adebug("api.exchange_post.failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bad refresh token"
        )
    except KeyExpiredError as e:
        log = log.bind(error=str(e))
        await log.adebug("api.exchange_post.expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired"
        )

    return key_content


@login_app.post(
    "/expire",
    summary="Expire a refresh token",
    description=(
        "Expire a refresh token on the backend, effectively logging the user out. "
        "You must provide the `refresh_token` in the request body."
    ),
    responses={
        200: {"description": "Refresh token expired successfully"},
        400: {"description": "Invalid or missing refresh token"},
    },
)
async def expire(
    content: RefreshTokenModel,
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
):
    try:
        await flow_service.logout(
            encoded_refresh_key=content.refresh_token,
            settings=settings,
            conn=conn,
            log=log,
        )
    except (refresh_service.AuthorizationError, KeyExpiredError):
        # I mean, we can't decode it so it's not valid, I don't care.
        pass


@login_app.delete(
    "/expire/{refresh_key_id}",
    summary="Expire a refresh token",
    description=(
        "Expire a refresh token on the backend, effectively logging the user out. "
        "You must provide the `refresh_token` in the request body."
    ),
    responses={
        200: {"description": "Refresh token expired successfully"},
        404: {"description": "That key does not exist or you are not the owner"},
    },
)
async def expire_by_id(
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
    user: AuthenticatedUserDependency,
    refresh_key_id: UUID = Path(
        ...,
        description="The refresh token ID you want to expire; must be created by you.",
    ),
):
    log = log.bind(refresh_key_id=refresh_key_id, user=user)
    try:
        refresh_key = await refresh_service.read_by_id(
            refresh_key_id=refresh_key_id, conn=conn
        )

        if refresh_key.user_id != user.user_id:
            log.ainfo("api.login.expire.user_id_mismatch")
            raise refresh_service.AuthorizationError("Not your key")
    except refresh_service.AuthorizationError:
        await log.ainfo("api.login.expire.disallowed")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Key not found"
        )

    await refresh_service.expire_refresh_key_by_id(key_id=refresh_key_id, conn=conn)

    await log.ainfo("api.login.expire.success")

    return


if SETTINGS().host_development_only_endpoint:

    @login_app.get("/developer_details")
    async def developer_details(settings: SettingsDependency):
        """
        A simple endpoint detailing information about the applicaiton for
        development use (e.g. the self-contained APP ID)
        """

        return {
            "authentication_client_secret": settings.created_app_client_secret,
            "authentication_app_id": settings.created_app_id,
            "authentication_public_key": settings.created_app_public_key,
            "authentication_key_type": settings.key_pair_type,
        }
