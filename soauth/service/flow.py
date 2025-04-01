"""
Primary authentication flow - get your first refresh and access token.
Secondary authentication flow - exchange a refresh token for a new one and
a new access token.
"""

from soauth.database.user import User
from soauth.database.app import App
from soauth.config.settings import Settings
from .auth import create_auth_key
from .refresh import create_refresh_key, refresh_refresh_key, decode_refresh_key

from sqlalchemy.ext.asyncio import AsyncSession


async def primary(
    user: User, app: App, settings: Settings, conn: AsyncSession
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

    Returns
    -------
    encoded_auth_key
        Encoded authentication key for use by the client.
    encoded_refresh_key
        The new refresh key.
    """
    encoded_refresh_key, refresh_key = await create_refresh_key(
        user=user, app=app, settings=settings, conn=conn
    )

    encoded_auth_key = await create_auth_key(
        refresh_key=refresh_key, settings=Settings, conn=conn
    )

    return encoded_auth_key, encoded_refresh_key


async def secondary(
    encoded_refresh_key: str, settings: Settings, conn: AsyncSession
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
    decoded_payload = await decode_refresh_key(
        encoded_payload=encoded_refresh_key, conn=conn
    )

    encoded_refresh_key, refresh_key = await refresh_refresh_key(
        payload=decoded_payload, settings=settings, conn=conn
    )

    encoded_auth_key = create_auth_key(
        refresh_key=refresh_key, settings=settings, conn=conn
    )

    return encoded_auth_key, encoded_refresh_key
