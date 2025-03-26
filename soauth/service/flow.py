"""
Core functions for the auth flow, including connections to the GitHub APIs.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soauth.config.settings import Settings
from soauth.database.app import App
from soauth.database.auth import RefreshKey
from soauth.database.user import User


async def expire_refresh_keys(user: User, app: App, conn: AsyncSession):
    """
    Expires all refresh keys for a given user/app combination.
    """
    query = select(
        RefreshKey
    ).filter_by(RefreshKey.created_by == user.uid, RefreshKey.app_id == app.uid, RefreshKey.revoked == False)

    all_unexpired = (await conn.execute(query)).scalars().all()

    for key in all_unexpired:
        key.last_used = datetime.now()
        key.revoked = True

        conn.add(key)

    await conn.commit()

    return

async def create_refresh_key(user: User, app: App, settings: Settings, conn: AsyncSession):
    """
    Creates a 'fresh' refresh token for a user.
    """

    # We must make sure we have a singleton key - there can be only one!
    # This helps with race conditions, too.
    await expire_refresh_keys(user=user, app=app, conn=conn)

    create_time = datetime.now()
    expiry_time = create_time + settings.refresh_key_expiry

    refresh_key = RefreshKey(
        user_id = user.uid,
        app_id = app.uid,
        # content=$$$$,
        last_used=create_time,
        used=0,
        revoked=False,
        previous=None,
        created_by=user,
        created_at=create_time,
        expires_at=expiry_time
    )




