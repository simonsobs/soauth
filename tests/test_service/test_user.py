"""
Tests the user service
"""

import pytest

from soauth.service import groups as group_service
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
            USER_NAME = user.user_name

    async with session_manager.session() as conn:
        async with conn.begin():
            await user_service.add_grant(
                user_name="test_user", grant="test_grant", conn=conn, log=logger
            )

    async with session_manager.session() as conn:
        async with conn.begin():
            user = await user_service.read_by_id(user_id=USER_ID, conn=conn)

            assert len(user.groups) > 0
            assert user.has_effective_grant("test_grant")

    async with session_manager.session() as conn:
        async with conn.begin():
            await user_service.remove_grant(
                user_name="test_user", grant="test_grant", conn=conn, log=logger
            )

    async with session_manager.session() as conn:
        async with conn.begin():
            user = await user_service.read_by_id(user_id=USER_ID, conn=conn)

            assert not user.has_effective_grant("test_grant")

    async with session_manager.session() as conn:
        async with conn.begin():
            await user_service.delete(user_name="test_user", conn=conn, log=logger)

    with pytest.raises(user_service.UserNotFound):
        async with session_manager.session() as conn:
            async with conn.begin():
                user = await user_service.read_by_id(user_id=USER_ID, conn=conn)

    with pytest.raises(user_service.UserNotFound):
        async with session_manager.session() as conn:
            async with conn.begin():
                user = await user_service.read_by_name(user_name=USER_NAME, conn=conn)


@pytest.mark.asyncio(loop_scope="session")
async def test_user_effective_grants_with_group(server_settings, session_manager, logger):
    async with session_manager.session() as conn:
        async with conn.begin():
            # Create a new user
            user = await user_service.create(
                user_name="test_user",
                email="test_user@email.com",
                full_name="Test User Group Grants",
                grants="user_grant",
                conn=conn,
                log=logger,
            )
            USER_ID = user.user_id

            # Create a new group with grants and add the user
            group = await group_service.create(
                group_name="test_group_with_grants",
                created_by_user_id=USER_ID,
                member_ids=[USER_ID],
                grants="group_grant another_group_grant",
                conn=conn,
                log=logger,
            )
            GROUP_ID = group.group_id

    async with session_manager.session() as conn:
        async with conn.begin():
            # Read the user and check effective grants
            user = await user_service.read_by_id(user_id=USER_ID, conn=conn)
            effective_grants = user.get_effective_grants()

            assert "user_grant" in effective_grants
            assert "group_grant" in effective_grants
            assert "another_group_grant" in effective_grants
            assert user.has_effective_grant("user_grant")
            assert user.has_effective_grant("group_grant")
            assert user.has_effective_grant("another_group_grant")
            assert not user.has_effective_grant("non_existent_grant")

    async with session_manager.session() as conn:
        async with conn.begin():
            # Delete the group
            await group_service.delete_group(group_id=GROUP_ID, conn=conn, log=logger)


@pytest.mark.asyncio(loop_scope="session")
async def test_user_with_no_groups(server_settings, session_manager, logger):
    async with session_manager.session() as conn:
        async with conn.begin():
            user = await user_service.create(
                user_name="test_user_no_groups",
                email="test@user.com",
                full_name="Test User No Groups",
                grants="",
                conn=conn,
                log=logger,
            )
            USER_ID = user.user_id
            GROUP_ID = user.groups[0].group_id

    # Delete the auto-created group for the user
    async with session_manager.session() as conn:
        async with conn.begin():
            await group_service.delete_group(group_id=GROUP_ID, conn=conn, log=logger)

    async with session_manager.session() as conn:
        async with conn.begin():
            user = await user_service.read_by_id(user_id=USER_ID, conn=conn)
            user.to_core(include_groups=True)
            assert len(user.groups) == 0

    async with session_manager.session() as conn:
        async with conn.begin():
            await user_service.delete(
                user_name="test_user_no_groups", conn=conn, log=logger
            )
