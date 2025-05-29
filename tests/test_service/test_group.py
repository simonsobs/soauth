"""
Tests the group service layer.
"""

import pytest

from soauth.service import groups as groups_service
from soauth.service import user as user_service


@pytest.mark.asyncio(loop_scope="session")
async def test_create_group(server_settings, session_manager, logger, user):
    async with session_manager.session() as conn:
        async with conn.begin():
            group = await groups_service.create(
                group_name="test_new_group",
                created_by_user_id=user,
                member_ids=[user],
                conn=conn,
                log=logger,
            )

            GROUP_ID = group.group_id

    # Try to create it again
    with pytest.raises(groups_service.GroupExistsError):
        async with conn.begin():
            group = await groups_service.create(
                group_name="test_new_group",
                created_by_user_id=user,
                member_ids=[user],
                conn=conn,
                log=logger,
            )

    # Read by ID
    async with session_manager.session() as conn:
        async with conn.begin():
            group = await groups_service.read_by_id(
                group_id=GROUP_ID, conn=conn, log=logger
            )

            assert group.group_name == "test_new_group"
            assert group.created_by_user_id == user
            assert len(group.members) == 1
            assert group.members[0].user_id == user

    # Read by name
    async with session_manager.session() as conn:
        async with conn.begin():
            group = await groups_service.read_by_name(
                group_name="test_new_group", conn=conn, log=logger
            )

            assert group.group_id == GROUP_ID
            assert group.created_by_user_id == user
            assert len(group.members) == 1
            assert group.members[0].user_id == user

    # Create a second user and add them to the group, test they live there
    # remove them, and then delete the user.
    async with session_manager.session() as conn:
        async with conn.begin():
            user2 = await user_service.create(
                user_name="test_user2",
                email="asfasdf@salsdfasd.com",
                full_name="Test User 2",
                grants="",
                conn=conn,
                log=logger,
            )
            USER2_ID = user2.user_id
            await groups_service.add_member(
                group_id=GROUP_ID, user_id=user2.user_id, conn=conn, log=logger
            )
            group = await groups_service.read_by_id(
                group_id=GROUP_ID, conn=conn, log=logger
            )
            assert len(group.members) == 2
            assert group.members[1].user_id == user2.user_id

    async with session_manager.session() as conn:
        async with conn.begin():
            await groups_service.remove_member(
                group_id=GROUP_ID, user_id=USER2_ID, conn=conn, log=logger
            )
            group = await groups_service.read_by_id(
                group_id=GROUP_ID, conn=conn, log=logger
            )
            assert len(group.members) == 1
            assert group.members[0].user_id == user

    async with session_manager.session() as conn:
        async with conn.begin():
            await user_service.delete(user_name="test_user2", conn=conn, log=logger)

    # Delete the group
    async with session_manager.session() as conn:
        async with conn.begin():
            await groups_service.delete_group(group_id=GROUP_ID, conn=conn, log=logger)

    # Try to read the group again
    async with session_manager.session() as conn:
        async with conn.begin():
            with pytest.raises(groups_service.GroupNotFound):
                group = await groups_service.read_by_id(
                    group_id=GROUP_ID, conn=conn, log=logger
                )


@pytest.mark.asyncio(loop_scope="session")
async def test_create_empty_group(server_settings, session_manager, logger, user):
    async with session_manager.session() as conn:
        async with conn.begin():
            group = await groups_service.create(
                group_name="test_new_group",
                created_by_user_id=user,
                member_ids=[],
                conn=conn,
                log=logger,
            )

            group_content = group.to_core()
            GROUP_ID = group.group_id

    # Delete the group
    async with session_manager.session() as conn:
        async with conn.begin():
            await groups_service.delete_group(group_id=GROUP_ID, conn=conn, log=logger)
