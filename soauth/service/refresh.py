"""
Core functions for the auth flow, including connections to the GitHub APIs.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import false, select
from sqlalchemy.ext.asyncio import AsyncSession

from soauth.config.settings import Settings
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
    )

    all_unexpired = (await conn.execute(query)).scalars().all()

    for key in all_unexpired:
        key.last_used = datetime.now(timezone.utc)
        key.revoked = True

        conn.add(key)

    return


async def create_refresh_key(
    user: User, app: App, settings: Settings, conn: AsyncSession
) -> tuple[str, RefreshKey]:
    """
    Creates a 'fresh' refresh token for a user, stores it in the database,
    and returns the encrypted payload.
    """

    # We must make sure we have a singleton key - there can be only one!
    # This helps with race conditions, too.
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

    # UUIDs are serialized to integers
    if isinstance(app_id, int):
        app_id = UUID(hex=app_id)

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
    payload: dict[str, Any], settings: Settings, conn: AsyncSession
) -> tuple[str, RefreshKey]:
    """
    Perform the key refresh flow. This:

    1. Checks that the payload corresponds to an active key.
    2. Revokes that key.
    3. Refreshes the content of the key payload, re-signs it, and returns for use
    """

    uuid = payload["uuid"]

    if isinstance(uuid, int):
        uuid = UUID(hex=uuid)

    res = await conn.get(RefreshKey, uuid)

    if res is None:
        raise AuthorizationError(f"Prior key not found ({uuid})")

    if res.revoked:
        raise AuthorizationError("Key used for refresh has been revoked")

    # We have an active key.
    new_payload = refresh_refresh_key_payload(payload)
    app = await conn.get(App, res.app_id)

    create_time = new_payload["iat"]
    expiry_time = new_payload["exp"]
    uuid = new_payload["uuid"]

    # TODO: should we not check against GitHub to update the user's info
    #       here? We could have a service function reverify_user that does
    #       this for us.

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
        revoked=False,
        previous=res.refresh_key_id,
        created_by=res.user_id,
        created_at=create_time,
        expires_at=expiry_time,
    )

    res.revoked = True
    res.used += 1
    res.last_used = create_time

    conn.add(refresh_key)
    conn.add(res)

    return content, refresh_key


async def expire_refresh_key(
    payload: dict[str, Any], settings: Settings, conn: AsyncSession
):
    """
    Expire a refresh key based upon its payload.
    """

    uuid = payload["uuid"]

    if isinstance(uuid, int):
        uuid = UUID(hex=uuid)

    res = await conn.get(RefreshKey, uuid)

    if res is None:
        return

    res.last_used = datetime.now(timezone.utc)
    res.revoked = True

    conn.add(res)
    await conn.commit()

    return
