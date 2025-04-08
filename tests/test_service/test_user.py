"""
Tests the user service
"""

import pytest

from soauth.service import user as user_service


@pytest.mark.asyncio(loop_scope="session")
async def test_create_user(server_settings, session_manager, logger):
    async with session_manager.session() as conn:
        async with conn.begin():
            user = await user_service.create(
                user_name="test_user",
                email="test_user@email.com",
                full_name="Test User",
                grants="",
                conn=conn,
                log=logger,
            )

            USER_ID = user.user_id

    async with session_manager.session() as conn:
        async with conn.begin():
            await user_service.add_grant(
                user_name="test_user", grant="test_grant", conn=conn, log=logger
            )

    async with session_manager.session() as conn:
        async with conn.begin():
            user = await user_service.read_by_id(user_id=USER_ID, conn=conn)

            assert user.has_grant("test_grant")

    async with session_manager.session() as conn:
        async with conn.begin():
            await user_service.remove_grant(
                user_name="test_user", grant="test_grant", conn=conn, log=logger
            )

    async with session_manager.session() as conn:
        async with conn.begin():
            user = await user_service.read_by_id(user_id=USER_ID, conn=conn)

            assert not user.has_grant("test_grant")

    async with session_manager.session() as conn:
        async with conn.begin():
            await user_service.delete(user_name="test_user", conn=conn, log=logger)

    with pytest.raises(user_service.UserNotFound):
        async with session_manager.session() as conn:
            async with conn.begin():
                user = await user_service.read_by_id(user_id=USER_ID, conn=conn)
