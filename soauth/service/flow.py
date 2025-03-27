"""
Core functions for the auth flow, including connections to the GitHub APIs.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from soauth.core.hashing import checksum

from soauth.config.settings import Settings
from soauth.database.app import App
from soauth.database.auth import RefreshKey
from soauth.database.user import User
from soauth.core.tokens import build_refresh_key_payload, sign_payload


async def expire_refresh_keys(user: User, app: App, conn: AsyncSession):
    """
    Expires all refresh keys for a given user/app combination.
    """
    query = select(RefreshKey).filter_by(
        RefreshKey.created_by == user.uid,
        RefreshKey.app_id == app.uid,
        RefreshKey.revoked is False,
    )

    all_unexpired = (await conn.execute(query)).scalars().all()

    for key in all_unexpired:
        key.last_used = datetime.now()
        key.revoked = True

        conn.add(key)

    await conn.commit()

    return


async def create_refresh_key(
    user: User, app: App, settings: Settings, conn: AsyncSession
) -> tuple[str, RefreshKey]:
    """
    Creates a 'fresh' refresh token for a user.
    """

    # We must make sure we have a singleton key - there can be only one!
    # This helps with race conditions, too.
    await expire_refresh_keys(user=user, app=app, conn=conn)

    payload = build_refresh_key_payload(
        user_id=user.uid,
        app_id=app.uid,
        validity=settings.refresh_key_expiry
    )

    create_time = payload["iat"]
    expiry_time = payload["exp"]
    uuid = payload["uuid"]

    content = sign_payload(
        key_password=settings.key_password,
        private_key=app.private_key,
        key_pair_type=app.key_pair_type,
        payload=payload,
    )

    hashed_content = checksum(content=content, hash_algorithm=settings.hash_algorithm)

    refresh_key = RefreshKey(
        uuid=uuid,
        user_id=user.uid,
        app_id=app.uid,
        hash_algorithm=settings.hash_algorithm,
        hashed_content=hashed_content,
        content=content,
        last_used=create_time,
        used=0,
        revoked=False,
        previous=None,
        created_by=user,
        created_at=create_time,
        expires_at=expiry_time,
    )

    return content, refresh_key