"""
Login request handling.
"""

from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from soauth.config.settings import Settings
from soauth.core.uuid import UUID
from soauth.database.app import App
from soauth.database.login import LoginRequest
from soauth.database.user import User
from soauth.service import app as app_service


class StaleRequestError(Exception):
    pass


class RedirectInvalidError(Exception):
    pass


async def expire_stale_requests(settings: Settings, conn: AsyncSession):
    """
    Expires all stale requests according to the settings timeout.
    """

    current_time = datetime.now(timezone.utc)
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


async def create(
    app: App, redirect_to: str | None, conn: AsyncSession, log: FilteringBoundLogger
) -> LoginRequest:
    """
    Create a fresh login request, including the eventual redirection
    location.
    """

    log = log.bind(app_id=app.app_id, redirect_to=redirect_to)

    request = LoginRequest(
        app_id=app.app_id,
        redirect_to=redirect_to,
        initiated_at=datetime.now(timezone.utc),
    )

    conn.add(request)

    await log.ainfo("login.request_created")

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
            f"Application host and redirection host are not the same {redirect_host} v.s. {app_host}"
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


async def read_by_code(code: str, secret: str, conn: AsyncSession) -> LoginRequest:
    """
    Read a login request by its secret code, and validate that the
    secret is valid.

    Parameters
    ----------
    code: str
        The secret code that can be exchanged by downstream applications
        for keys.
    secret: str
        The secret key for the application the user is authenticating
        against.
    conn: AsyncSession
        Database connection.

    Raises
    ------
    StaleRequestError
        In the case where the request is either not found, or it
        has been marked as stale.
    """

    login_request = (
        await conn.execute(
            select(LoginRequest).filter(LoginRequest.secret_code == code)
        )
    ).scalar_one_or_none()

    if login_request is None:
        raise StaleRequestError("Secret key not found")

    app = await app_service.read_by_id(app_id=login_request.app_id, conn=conn)

    if app.client_secret != secret:
        raise StaleRequestError("Client secret incorrect")

    return login_request


async def complete(
    login_request: LoginRequest | None,
    user: User,
    conn: AsyncSession,
    log: FilteringBoundLogger,
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

    log = log.bind(
        login_request_id=login_request.login_request_id,
        app_id=login_request.app_id,
        user_id=user.user_id,
        redirect_to=login_request.redirect_to,
        initiated_at=login_request.initiated_at,
    )

    if login_request is None or login_request.stale:
        await log.ainfo("login.request_stale")
        raise StaleRequestError("Login request not found or stale")

    app = await app_service.read_by_id(login_request.app_id, conn)

    try:
        login_request.redirect_to = await build_redirect(
            user=user, app=app, request=login_request
        )
    except RedirectInvalidError as e:
        log = log.bind(login_request=login_request)
        await log.aerror("login.redirect_invalid")
        raise e

    login_request.completed_at = datetime.now(timezone.utc)
    login_request.user_id = user.user_id

    log = log.bind(
        redirect_to=login_request.redirect_to, completed_at=login_request.completed_at
    )

    conn.add(login_request)

    await log.ainfo("login.request_complete")

    return login_request.redirect_to
