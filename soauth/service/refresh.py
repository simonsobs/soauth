"""
Core functions for the auth flow, including connections to the GitHub APIs.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import false, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from soauth.config.settings import Settings
from soauth.core.app import LoggedInUserData
from soauth.core.hashing import checksum
from soauth.core.tokens import (
    KeyDecodeError,
    app_id_from_signed_payload,
    build_refresh_key_payload,
    reconstruct_payload,
    refresh_refresh_key_payload,
    sign_payload,
)
from soauth.core.uuid import UUID
from soauth.database.app import App
from soauth.database.auth import RefreshKey
from soauth.database.user import User
from soauth.service import user as user_service
from soauth.service.provider import AuthProvider


class AuthorizationError(Exception):
    pass


async def expire_refresh_keys(user: User, app: App, conn: AsyncSession):
    """
    Expires all refresh keys for a given user/app combination.
    """
    query = select(RefreshKey).filter(
        RefreshKey.user_id == user.user_id,
        RefreshKey.app_id == app.app_id,
        RefreshKey.revoked == false(),
        # We only care about restricting keys used for web sessions;
        # users can have as many API keys as they wish active at any
        # given time. They are responsible for managing them.
        RefreshKey.api_key == false(),
    )

    all_unexpired = (await conn.execute(query)).scalars().all()

    for key in all_unexpired:
        key.last_used = datetime.now(timezone.utc)
        key.revoked = True

        conn.add(key)

    return


async def create_refresh_key(
    user: User, app: App, api_key: bool, settings: Settings, conn: AsyncSession
) -> tuple[str, RefreshKey]:
    """
    Creates a 'fresh' refresh token for a user, stores it in the database,
    and returns the encrypted payload. `api_key` is a boolean describing
    whether this is an API key or a regular 'login' token used for web
    access. As many API keys may be allowed as the user wants, but there
    can only be one active web session.
    """

    # We must make sure we have a singleton key - there can be only one!
    # This helps with race conditions, too.
    if not api_key:
        await expire_refresh_keys(user=user, app=app, conn=conn)

    payload = build_refresh_key_payload(
        user_id=user.user_id, app_id=app.app_id, validity=settings.refresh_key_expiry
    )

    create_time = payload["iat"]
    expiry_time = payload["exp"]
    uuid = payload["uuid"]

    content = sign_payload(
        app_id=app.app_id,
        key_password=settings.key_password,
        private_key=app.private_key,
        key_pair_type=app.key_pair_type,
        payload=payload,
    )

    hashed_content = checksum(content=content, hash_algorithm=settings.hash_algorithm)

    refresh_key = RefreshKey(
        refresh_key_id=uuid,
        user_id=user.user_id,
        app_id=app.app_id,
        hash_algorithm=settings.hash_algorithm,
        hashed_content=hashed_content,
        last_used=create_time,
        used=0,
        api_key=api_key,
        revoked=False,
        previous=None,
        created_at=create_time,
        expires_at=expiry_time,
    )

    conn.add(refresh_key)

    return content, refresh_key


async def decode_refresh_key(
    encoded_payload: str | bytes, conn: AsyncSession
) -> dict[str, Any]:
    """
    Decodes a refresh key's payload, but _does not_ verify that it is
    a valid key (i.e. it is not checked against the database; see
    `refresh_refresh_key` which should be used when generating access
    tokens).

    If the token passes this, we can be sure that we emitted it as it
    has been successfully verified through the key pair stored in the
    application.
    """

    try:
        app_id = app_id_from_signed_payload(encoded_payload)
    except KeyDecodeError:
        raise AuthorizationError(
            "Unable to reconstruct the application ID from the key"
        )

    app = await conn.get(App, app_id)

    if app is None:
        raise AuthorizationError(f"No app with ID {app_id}")

    try:
        reconstructed_payload = reconstruct_payload(
            webtoken=encoded_payload,
            public_key=app.public_key,
            key_pair_type=app.key_pair_type,
        )
    except KeyDecodeError:
        raise AuthorizationError("Error decoding content of web token")

    return reconstructed_payload


async def refresh_refresh_key(
    payload: dict[str, Any],
    settings: Settings,
    conn: AsyncSession,
    log: FilteringBoundLogger,
    provider: AuthProvider,
) -> tuple[str, RefreshKey]:
    """
    Perform the key refresh flow. This:

    1. Checks that the payload corresponds to an active key.
    2. Revokes that key.
    3. Refreshes the user against GitHub, for when the access key must be created
    4. Refreshes the content of the key payload, re-signs it, and returns for use
    """

    uuid = payload["uuid"]

    if isinstance(uuid, int):
        uuid = UUID(hex=uuid)

    res = await conn.get(RefreshKey, uuid)

    if res is None:
        raise AuthorizationError(f"Prior key not found ({uuid})")

    if res.revoked:
        raise AuthorizationError("Key used for refresh has been revoked")

    if (uid := UUID(hex=payload["user_id"])) != res.user_id:
        raise AuthorizationError(
            f"User ID does not match database {uid} v.s. {res.user_id}!"
        )

    # We have an active key.
    new_payload = refresh_refresh_key_payload(payload)
    app = await conn.get(App, res.app_id)

    create_time = new_payload["iat"]
    expiry_time = new_payload["exp"]
    uuid = new_payload["uuid"]

    if isinstance(create_time, int):
        create_time = datetime.fromtimestamp(create_time)

    if isinstance(expiry_time, int):
        expiry_time = datetime.fromtimestamp(expiry_time)

    content = sign_payload(
        app_id=app.app_id,
        key_password=settings.key_password,
        private_key=app.private_key,
        key_pair_type=app.key_pair_type,
        payload=new_payload,
    )

    hashed_content = checksum(content=content, hash_algorithm=settings.hash_algorithm)

    refresh_key = RefreshKey(
        refresh_key_id=uuid,
        user_id=res.user_id,
        app_id=res.app_id,
        hash_algorithm=settings.hash_algorithm,
        hashed_content=hashed_content,
        last_used=create_time,
        used=0,
        api_key=res.api_key,
        revoked=False,
        previous=res.refresh_key_id,
        created_by=res.user_id,
        created_at=create_time,
        expires_at=res.expires_at,
    )

    res.revoked = True
    res.used += 1
    res.last_used = create_time

    conn.add(refresh_key)
    conn.add(res)

    # Check against GitHub for this user
    try:
        user = await user_service.read_by_id(user_id=refresh_key.user_id, conn=conn)
    except user_service.UserNotFound:
        raise AuthorizationError(f"User {refresh_key.user_id} not found")

    user = await provider.refresh(user=user, settings=settings, conn=conn, log=log)

    return content, refresh_key


async def read_by_id(refresh_key_id: UUID, conn: AsyncSession) -> RefreshKey:
    key = await conn.get(RefreshKey, refresh_key_id)

    if key is None:
        raise AuthorizationError("Key not found")

    return key


async def expire_refresh_key(
    payload: dict[str, Any], settings: Settings, conn: AsyncSession
):
    """
    Expire a refresh key based upon its payload.
    """

    uuid = payload["uuid"]

    if isinstance(uuid, int):
        uuid = UUID(hex=uuid)

    await expire_refresh_key_by_id(key_id=uuid, conn=conn)

    return


async def expire_refresh_key_by_id(key_id: UUID, conn: AsyncSession):
    """
    Force-expire a refresh key based upon its id.
    """

    res = await conn.get(RefreshKey, key_id)

    if res is None:
        return

    if res.revoked:
        return

    res.last_used = datetime.now(timezone.utc)
    res.revoked = True

    conn.add(res)
    await conn.commit()

    return


async def get_all_logins_for_user(
    user_id: UUID, conn: AsyncSession, log: FilteringBoundLogger
) -> list[LoggedInUserData]:
    """
    Get all logins for a user. This is useful for showing the user
    all their active sessions.
    """

    log = log.bind(user_id=user_id)

    query = (
        select(
            RefreshKey.refresh_key_id,
            RefreshKey.app_id,
            User.user_name,
            RefreshKey.created_at,
            RefreshKey.last_used,
            RefreshKey.expires_at,
            User.user_id,
            RefreshKey.api_key,
            App.app_name,
        )
        .filter(RefreshKey.user_id == user_id, RefreshKey.revoked == false())
        .join(RefreshKey.user)
        .join(RefreshKey.app)
    )

    result = await conn.execute(query)

    def unpack(x):
        return LoggedInUserData(
            refresh_key_id=x[0],
            app_id=x[1],
            user_name=x[2],
            first_authenticated=x[3],
            last_authenticated=x[4],
            login_expires=x[5],
            user_id=x[6],
            api_key=x[7],
            app_name=x[8],
        )

    unpacked = [unpack(x) for x in result]

    log = log.bind(number_of_logins=len(unpacked))

    await log.ainfo("refresh.all_logins")

    return unpacked


async def get_logged_in_users(
    app_id: UUID, conn: AsyncSession, log: FilteringBoundLogger
) -> list[LoggedInUserData]:
    """
    Get users that are 'logged in' (i.e. have refresh keys) for an application.
    """

    log = log.bind(app_id=app_id)

    query = (
        select(
            RefreshKey.refresh_key_id,
            User.user_name,
            RefreshKey.created_at,
            RefreshKey.last_used,
            RefreshKey.expires_at,
            RefreshKey.app_id,
            User.user_id,
            RefreshKey.api_key,
            App.app_name,
        )
        .filter(RefreshKey.app_id == app_id, RefreshKey.revoked == false())
        .join(RefreshKey.user)
        .join(RefreshKey.app)
    )

    result = await conn.execute(query)

    def unpack(x):
        return LoggedInUserData(
            refresh_key_id=x[0],
            user_name=x[1],
            first_authenticated=x[2],
            last_authenticated=x[3],
            login_expires=x[4],
            app_id=x[5],
            user_id=x[6],
            api_key=x[7],
            app_name=x[8],
        )

    unpacked = [unpack(x) for x in result]

    log = log.bind(number_of_users=len(unpacked))

    await log.ainfo("refresh.all_users")

    return unpacked
