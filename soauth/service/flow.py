"""
Primary authentication flow - get your first refresh and access token.
Secondary authentication flow - exchange a refresh token for a new one and
a new access token.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from soauth.config.settings import Settings
from soauth.core.uuid import UUID
from soauth.database.app import App
from soauth.database.user import User

from .auth import create_auth_key
from .refresh import (
    AuthorizationError,
    KeyDecodeError,
    create_refresh_key,
    decode_refresh_key,
    expire_refresh_key,
    refresh_refresh_key,
)


async def primary(
    user: User,
    app: App,
    settings: Settings,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> tuple[str]:
    """
    Primary authentication flow - assumes that you just created the 'user'
    and that the 'user' has _all required credentials, grants and groups_.
    This function simply creates the required access and refresh tokens.
    Once you give out the access token, users can authenticate with services.
    A refresh token allows them to continually re-authenticate with the
    service, so be extra careful with that!

    Parameters
    ----------
    user
        The user to create access/refresh tokens for.
    app
        The app to create the refresh token for.
    settings
        Server settings.
    conn
        Database session.
    log
        StructLog logger to use.

    Returns
    -------
    encoded_auth_key
        Encoded authentication key for use by the client.
    encoded_refresh_key
        The new refresh key.
    """
    log = log.bind(user_id=user.user_id, app_id=app.app_id)
    encoded_refresh_key, refresh_key = await create_refresh_key(
        user=user, app=app, settings=settings, conn=conn
    )
    log = log.bind(refresh_key_id=refresh_key.refresh_key_id)
    await log.ainfo("primary.refresh_key_created")

    log = log.bind(
        user_id=refresh_key.user_id,
        app_id=refresh_key.app_id,
        refresh_key_id=refresh_key.refresh_key_id,
    )

    encoded_auth_key = await create_auth_key(
        refresh_key=refresh_key, settings=settings, conn=conn
    )
    await log.ainfo("primary.auth_key_created")

    return encoded_auth_key, encoded_refresh_key


async def secondary(
    encoded_refresh_key: str,
    settings: Settings,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> tuple[str]:
    """
    Secondary authentication flow - turn in your encoded refresh key
    for a new one and an authentication key. This checks against
    things like refresh time and whether this is a singleton.

    Parameters
    ----------
    encoded_refresh_key
        The refresh key recieved from the client.
    settings
        Server settings.
    conn
        Database sesssion (async)

    Returns
    -------
    encoded_auth_key
        Encoded authentication key for use by the client.
    encoded_refresh_key
        The new refresh key.
    """
    log.debug("secondary.decoding_key")
    decoded_payload = await decode_refresh_key(
        encoded_payload=encoded_refresh_key, conn=conn
    )

    log = log.bind(
        user_id=UUID(hex=decoded_payload["user_id"]),
        app_id=UUID(hex=decoded_payload["app_id"]),
        old_issued_at=decoded_payload["iat"],
        old_expiry_time=decoded_payload["exp"],
        old_refresh_key_id=UUID(hex=decoded_payload["uuid"]),
    )

    encoded_refresh_key, refresh_key = await refresh_refresh_key(
        payload=decoded_payload, settings=settings, conn=conn
    )

    log = log.bind(
        new_refresh_key_id=refresh_key.refresh_key_id,
    )

    await log.ainfo("secondary.refresh_key_exchanged")

    encoded_auth_key = await create_auth_key(
        refresh_key=refresh_key, settings=settings, conn=conn
    )

    log = log.bind(
        user_id=refresh_key.user_id,
        app_id=refresh_key.app_id,
        refresh_key_id=refresh_key.refresh_key_id,
    )

    await log.ainfo("secondary.auth_key_created")

    return encoded_auth_key, encoded_refresh_key


async def logout(
    encoded_refresh_key: str,
    settings: Settings,
    conn: AsyncSession,
    log: FilteringBoundLogger,
):
    """
    Expire a refresh key in the database and log out.
    """

    try:
        decoded_payload = await decode_refresh_key(
            encoded_payload=encoded_refresh_key, conn=conn
        )
    except (AuthorizationError, KeyDecodeError):
        # Their refresh key was never valid anyway!
        await log.ainfo("logout.invalid_refresh_key")
        return

    log = log.bind(
        user_id=UUID(hex=decoded_payload["user_id"]),
        app_id=UUID(hex=decoded_payload["app_id"]),
        issued_at=decoded_payload["iat"],
        expiry_time=decoded_payload["exp"],
        refresh_key_id=UUID(hex=decoded_payload["uuid"]),
    )

    await expire_refresh_key(payload=decoded_payload, settings=settings, conn=conn)

    await log.ainfo("logout.completed")

    return
