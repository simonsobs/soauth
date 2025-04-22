"""
Test for app creation/deletion functionality
"""

import pytest

from soauth.service import app as app_service
from soauth.service import user as user_service


@pytest.mark.asyncio(loop_scope="session")
async def test_create_app(user, session_manager, server_settings, logger):
    async with session_manager.session() as conn:
        async with conn.begin():
            app = await app_service.create(
                domain="https://simonsobs.org",
                user=await user_service.read_by_id(user_id=user, conn=conn),
                redirect_url="https://simonsobs.org/callback",
                settings=server_settings,
                conn=conn,
                log=logger,
            )

            APP_ID = app.app_id

    async with session_manager.session() as conn:
        async with conn.begin():
            app = await app_service.read_by_id(
                app_id=APP_ID,
                conn=conn,
            )

            assert app.domain == "https://simonsobs.org"
            assert app.client_secret is not None

            OLD_KEY = app.private_key
            OLD_CLIENT_SECRET = app.client_secret

    async with session_manager.session() as conn:
        async with conn.begin():
            await app_service.refresh_keys(
                app_id=APP_ID, settings=server_settings, conn=conn, log=logger
            )

    async with session_manager.session() as conn:
        async with conn.begin():
            app = await app_service.read_by_id(
                app_id=APP_ID,
                conn=conn,
            )
            assert app.private_key != OLD_KEY
            assert app.client_secret != OLD_CLIENT_SECRET

    async with session_manager.session() as conn:
        async with conn.begin():
            await app_service.delete(
                app_id=APP_ID,
                conn=conn,
                log=logger,
            )

    with pytest.raises(app_service.AppNotFound):
        async with session_manager.session() as conn:
            async with conn.begin():
                app = await app_service.read_by_id(app_id=APP_ID, conn=conn)
