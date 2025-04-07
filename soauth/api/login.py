"""
Main login flow - redirection to GitHub and handling of responses.
"""

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from soauth.service import app as app_service
from soauth.service import flow as flow_service
from soauth.service import github as github_service
from soauth.service import login as login_service
from soauth.service import refresh as refresh_service

from .dependencies import DatabaseDependency, SettingsDependency

login_router = APIRouter()


@login_router.get("/login/{app_id}")
async def login(
    app_id: uuid.uuid7,
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
) -> RedirectResponse:
    """
    Login flow - use this to be redirected to GitHub for login, and have
    your session validated.

    You will be redirected either to the main page of your registered app,
    or (preferentially) you will be redirected to the URL defined in your
    `Referer` header.
    """
    try:
        app = await app_service.read_by_id(uid=app_id, conn=conn)
    except app_service.AppNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"App {app_id} not found")

    login_request = await login_service.create(
        app=app, redirect_to=request.headers.get("Referer", None), conn=conn
    )

    redirect_url = await github_service.github_login_redirect(
        login_request=login_request, settings=settings
    )

    return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)


@login_router.get("/github")
async def github(
    code: str, state: uuid.uuid7, settings: SettingsDependency, conn: DatabaseDependency
) -> RedirectResponse:
    """
    This endpoint is 'called' by GitHub itself, and attempts to complete
    the login flow from GitHub.
    """

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
    )

    # Check that this login request is valid on our end, by reconstructing our
    # login request from the database.
    try:
        login_request = await login_service.read(login_request_id=state, conn=conn)
    except login_service.StaleRequestError:
        raise unauthorized

    # This calls GitHub upp and authenticates as the user, allowing us access
    # to user information and to actually validate the login
    try:
        user = await github_service.github_login(
            code=code, settings=settings, conn=conn
        )
    except github_service.GitHubLoginError:
        raise unauthorized

    # Create the codes!
    auth_key, refresh_key = await flow_service.primary(
        user=user, app=login_request.app, settings=settings, conn=conn
    )

    # Check in to make sure we're still valid and close out the login
    try:
        redirect = await login_service.complete(
            login_request=login_request, user=user, conn=conn
        )
    except (login_service.StaleRequestError, login_service.RedirectInvalidError):
        raise unauthorized

    response = RedirectResponse(url=redirect)

    response.set_cookie("access_token", auth_key, httponly=True)
    response.set_cookie("refresh_token", refresh_key, httponly=True)

    return response


@login_router.get("/exchange")
async def exchange(
    request: Request, settings: SettingsDependency, conn: DatabaseDependency
) -> RedirectResponse:
    """
    Exchange your refresh key for a new refresh key and a new auth key.

    You will be redirected back to the URL in your requests "Referer" header.
    """

    redirect = request.headers.get("Referer", None)

    if redirect is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your request must include a 'Referer' header",
        )

    try:
        auth_key, refresh_key = await flow_service.secondary(
            encoded_refresh_key=request.cookies.get("refresh_token", ""),
            settings=settings,
            conn=conn,
        )
    except refresh_service.AuthorizationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad refresh token"
        )

    response = RedirectResponse(url=redirect)

    response.set_cookie("access_token", auth_key, httponly=True)
    response.set_cookie("refresh_token", refresh_key, httponly=True)

    return response


@login_router.get("/logout")
async def logout(
    request: Request, settings: SettingsDependency, conn: DatabaseDependency
):
    """
    Log a user out and revoke the refresh key they are using. The user will be redirected
    back to the "Referer" header.
    """

    redirect = request.headers.get("Referer", None)

    if redirect is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your request must include a 'Referer' header",
        )

    try:
        await flow_service.logout(
            encoded_refresh_key=request.cookies.get("refresh_token", ""),
            settings=settings,
            conn=conn,
        )
    except refresh_service.AuthorizationError:
        # I mean, we can't decode it so it's not valid, I don't care.
        pass

    response = RedirectResponse(url=redirect)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return response
