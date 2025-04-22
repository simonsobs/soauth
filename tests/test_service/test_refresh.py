"""
Tests creation and revocation of refresh keys.
"""

import pytest

from soauth.database.auth import RefreshKey
from soauth.service import app as app_service
from soauth.service import refresh as refresh_service
from soauth.service import user as user_service


@pytest.mark.asyncio(loop_scope="session")
async def test_create_refresh_key(user, app, session_manager, logger, server_settings):
    async with session_manager.session() as conn:
        async with conn.begin():
            encoded, refresh_key = await refresh_service.create_refresh_key(
                user=await user_service.read_by_id(user, conn),
                app=await app_service.read_by_id(app, conn),
                settings=server_settings,
                conn=conn,
            )

            REFRESH_KEY_ID = refresh_key.refresh_key_id

    # Test we can decode it.
    async with session_manager.session() as conn:
        async with conn.begin():
            decoded = await refresh_service.decode_refresh_key(
                encoded_payload=encoded, conn=conn
            )

    assert decoded["uuid"] == REFRESH_KEY_ID.hex

    # Now create a new refresh key, and check that we expire the previous one
    async with session_manager.session() as conn:
        async with conn.begin():
            new_encoded, refresh_key = await refresh_service.create_refresh_key(
                user=await user_service.read_by_id(user, conn),
                app=await app_service.read_by_id(app, conn),
                settings=server_settings,
                conn=conn,
            )

            NEW_REFRESH_KEY_ID = refresh_key.refresh_key_id

    assert NEW_REFRESH_KEY_ID != REFRESH_KEY_ID

    async with session_manager.session() as conn:
        async with conn.begin():
            old_key = await conn.get(RefreshKey, REFRESH_KEY_ID)

            assert old_key.revoked

    # Now let's try to refresh our old revoked refresh key
    with pytest.raises(refresh_service.AuthorizationError):
        async with session_manager.session() as conn:
            async with conn.begin():
                decoded = await refresh_service.decode_refresh_key(
                    encoded_payload=encoded, conn=conn
                )
                await refresh_service.refresh_refresh_key(
                    payload=decoded, settings=server_settings, conn=conn, log=logger
                )

    # Now let's refresh our new refresh key.
    async with session_manager.session() as conn:
        async with conn.begin():
            decoded = await refresh_service.decode_refresh_key(
                encoded_payload=new_encoded, conn=conn
            )
            (
                refreshed_encoded,
                refreshed_refresh_key,
            ) = await refresh_service.refresh_refresh_key(
                payload=decoded, settings=server_settings, conn=conn, log=logger
            )
            REFRESHED_KEY_ID = refreshed_refresh_key.refresh_key_id
            assert refreshed_refresh_key.previous == NEW_REFRESH_KEY_ID

    async with session_manager.session() as conn:
        async with conn.begin():
            old_key = await conn.get(RefreshKey, NEW_REFRESH_KEY_ID)
            assert old_key.used == 1
            assert old_key.revoked

    async with session_manager.session() as conn:
        async with conn.begin():
            logged_in_users = await refresh_service.get_logged_in_users(
                app_id=app, conn=conn, log=logger
            )

            assert len(logged_in_users) > 0

    async with session_manager.session() as conn:
        async with conn.begin():
            pl = await refresh_service.decode_refresh_key(
                encoded_payload=refreshed_encoded, conn=conn
            )
            await refresh_service.expire_refresh_key(
                payload=pl, settings=server_settings, conn=conn
            )

    async with session_manager.session() as conn:
        async with conn.begin():
            old_key = await conn.get(RefreshKey, REFRESHED_KEY_ID)
            assert old_key.used == 0
            assert old_key.revoked
