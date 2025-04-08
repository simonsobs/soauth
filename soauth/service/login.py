"""
Login request handling.
"""

from soauth.core.uuid import uuid7, UUID
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from soauth.config.settings import Settings
from soauth.database.app import App
from soauth.database.login import LoginRequest
from soauth.database.user import User


class StaleRequestError(Exception):
    pass


class RedirectInvalidError(Exception):
    pass


async def expire_stale_requests(settings: Settings, conn: AsyncSession):
    """
    Expires all stale requests according to the settings timeout.
    """

    current_time = datetime.now()
    delete_before = current_time - settings.login_record_length
    stale_before = current_time - settings.stale_login_expiry

    query = delete(LoginRequest).where(LoginRequest.initiated_at < delete_before)

    await conn.execute(query)
    await conn.commit()

    query = (
        update(LoginRequest)
        .where(
            LoginRequest.stale is False,
            LoginRequest.completed_at is None,
            LoginRequest.initiated_at < stale_before,
        )
        .values(stale=True)
    )

    await conn.execute(query)
    await conn.commit()

    return


async def create(app: App, redirect_to: str | None, conn: AsyncSession) -> LoginRequest:
    """
    Create a fresh login request, including the eventual redirection
    location.
    """

    request = LoginRequest(
        app_id=app.app_id, redirect_to=redirect_to, initiated_at=datetime.now()
    )

    conn.add(request)
    await conn.commit()
    await conn.refresh(request)

    return request


async def build_redirect(user: User, app: App, request: LoginRequest) -> str:
    """
    Build a redirect URL for an app.

    Raises
    ------
    RedirectInvalidError
        In the case where the redirect location is not a path
        under the stated domain of the app.
    """

    redirect_to = request.redirect_to

    if redirect_to is None:
        redirect_to = app.domain

    app_host = urlparse(app.domain).hostname
    redirect_host = urlparse(redirect_to).hostname

    if app_host != redirect_host:
        raise RedirectInvalidError(
            "Application host and redirection host are not the same"
        )

    return redirect_to


async def read(login_request_id: UUID, conn: AsyncSession) -> LoginRequest:
    """
    Get a login request, and return it.

    Raises
    ------
    StaleRequestError
        In the case where the request is either not found, or it
        has been marked as stale.
    """

    login_request = await conn.get(LoginRequest, login_request_id)

    if login_request is None or login_request.stale:
        raise StaleRequestError("Login request not found or stale")

    return login_request


async def complete(
    login_request: LoginRequest | None, user: User, conn: AsyncSession
) -> str:
    """
    Complete a login request, generating the callback URL back to
    the app's service.

    Raises
    ------
    StaleRequestError
        In the case where the request is either not found, or it
        has been marked as stale.
    RedirectInvalidError
        In the case where the redirect location is not a path
        under the stated domain of the app.
    """

    if login_request is None or login_request.stale:
        raise StaleRequestError("Login request not found or stale")

    login_request.redirect_to = await build_redirect(
        user=user, app=login_request.app, request=login_request
    )
    login_request.completed_at = datetime.now()
    login_request.user_id = user.user_id

    conn.add(login_request)
    await conn.commit()

    return login_request.redirect_to
