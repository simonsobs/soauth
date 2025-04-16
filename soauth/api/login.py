"""
Main login flow - redirection to GitHub and handling of responses.
"""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from soauth.core.models import KeyRefreshResponse, RefreshTokenModel
from soauth.core.tokens import KeyExpiredError
from soauth.core.uuid import UUID
from soauth.service import app as app_service
from soauth.service import flow as flow_service
from soauth.service import github as github_service
from soauth.service import login as login_service
from soauth.service import refresh as refresh_service
from soauth.service import user as user_service

from .dependencies import (
    SETTINGS,
    DatabaseDependency,
    LoggerDependency,
    SettingsDependency,
)

login_app = APIRouter()


@login_app.get("/login/{app_id}")
async def login(
    app_id: UUID,
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> RedirectResponse:
    """
    Login flow - use this to be redirected to GitHub for login, and have
    your session validated.

    You will be redirected either to the main page of your registered app,
    or (preferentially) you will be redirected to the URL defined in your
    `Referer` header.
    """
    try:
        app = await app_service.read_by_id(app_id=app_id, conn=conn)
    except app_service.AppNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"App {app_id} not found")

    login_request = await login_service.create(
        app=app, redirect_to=request.headers.get("Referer", None), conn=conn, log=log
    )

    redirect_url = await github_service.github_login_redirect(
        login_request=login_request, settings=settings
    )

    log = log.bind(
        redirect_url=redirect_url, login_request_id=login_request.login_request_id
    )
    await log.ainfo("api.login.login.redirect")

    return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)


@login_app.get("/github")
async def github(
    code: str,
    state: UUID,
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> RedirectResponse:
    """
    This endpoint is 'called' by GitHub itself, and attempts to complete
    the login flow from GitHub.
    """

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
        user = await github_service.github_login(
            code=code, settings=settings, conn=conn, log=log
        )
        login_request.user_id = user.user_id
        conn.add(user)
    except github_service.GitHubLoginError:
        await log.aerror("api.login.github.github_error")
        raise unauthorized

    await log.ainfo("api.login.github.success")

    app = await app_service.read_by_id(app_id=login_request.app_id, conn=conn)

    # TODO: Parameterize this redirect process through a service layer.

    response = RedirectResponse(
        url=f"{app.redirect_url}?code={login_request.secret_code}&state={state}",
        status_code=302,
    )

    return response


@login_app.post("/code/{app_id}")
async def code(
    code: str,
    secret: str,
    app_id: UUID,
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> KeyRefreshResponse:
    """
    Exchange a code and client secret for keys.

    Returns a dictionary with access_token, refresh_token, and redirect - which is where
    you should redirect the user to after completing the exchange.
    """

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
    (
        auth_key,
        refresh_key,
        auth_key_expires,
        refresh_key_expires,
    ) = await flow_service.primary(
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
        access_token=auth_key,
        refresh_token=refresh_key,
        access_token_expires=auth_key_expires,
        refresh_token_expires=refresh_key_expires,
        redirect=redirect,
    )


@login_app.post("/exchange")
async def exchange_post(
    content: RefreshTokenModel,
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> KeyRefreshResponse:
    """
    Exchange your refresh key for a new refresh key and a new auth key.

    The refresh key should be passed as a POST parameter, and you will
    recieve back a JSON blob that contains:

    {"access_token": xxxx, "refresh_token": xxxx}
    """

    refresh_token = content.refresh_token

    try:
        (
            auth_key,
            refresh_key,
            auth_key_expires,
            refresh_key_expires,
        ) = await flow_service.secondary(
            encoded_refresh_key=refresh_token, settings=settings, conn=conn, log=log
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

    return KeyRefreshResponse(
        access_token=auth_key,
        refresh_token=refresh_key,
        access_token_expires=auth_key_expires,
        refresh_token_expires=refresh_key_expires,
    )


@login_app.post("/expire/{app_id}")
async def expire(
    app_id: UUID,
    content: RefreshTokenModel,
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
):
    """
    Expires a key.
    """

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
