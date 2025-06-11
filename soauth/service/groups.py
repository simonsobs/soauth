"""
Service layer for groups.
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from soauth.core.uuid import UUID
from soauth.database.group import Group

from . import user as user_service


class GroupNotFound(Exception):
    pass


class GroupExistsError(Exception):
    pass


async def create(
    group_name: str,
    created_by_user_id: UUID,
    member_ids: list[UUID],
    grants: str,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> Group:
    """
    Create a new group.

    Parameters
    ----------
    group_name: str
        The new group.
    created_by_user_id: UUID
        The user that created and has administration capabilities for this
        group.
    members: list[UUID]
        The list of users who should initially be in the group.
    grants: str
        A space separated string of grants to assign to the group.


    Raises
    ------
    sqlalchemy.exc.IntegrityError
        If a group with this name already exists.
    """

    group_name = group_name.strip().lower().replace(" ", "_")

    log = log.bind(
        group_name=group_name,
        user_id=created_by_user_id,
        number_of_members=len(member_ids),
        grants=grants,
    )

    try:
        created_by = await user_service.read_by_id(
            user_id=created_by_user_id, conn=conn
        )

        members = await asyncio.gather(
            *(
                user_service.read_by_id(user_id=user_id, conn=conn)
                for user_id in member_ids
            )
        )

        group = Group(
            group_name=group_name,
            created_by_user_id=created_by_user_id,
            created_by=created_by,
            created_at=datetime.now(tz=timezone.utc),
            members=list(members),
            grants=grants,
        )
        conn.add(group)
        await conn.flush()
    except user_service.UserNotFound as e:
        log = log.bind(member_ids=member_ids, error=e)
        await log.ainfo("group.user_does_not_exist")
        raise e
    except IntegrityError as e:
        log = log.bind(error=e)
        await log.ainfo("group.exists")
        raise GroupExistsError(f"Group {group_name} already exists")

    await log.ainfo("group.created")

    return group


async def get_group_list(
    conn: AsyncSession,
    log: FilteringBoundLogger,
    for_user: UUID | None = None,
) -> list[Group]:
    """
    Get a list of all groups.

    Parameters
    ----------
    conn: AsyncSession
        The database session.
    log: FilteringBoundLogger
        Logger instance.

    Returns
    -------
    list[Group]
        A list of all groups in the database.
    """
    log = log.bind(for_user=for_user)
    if for_user:
        result = await conn.execute(
            select(Group).join(Group.members).where(Group.members.any(user_id=for_user))
        )
    else:
        result = await conn.execute(select(Group))

    groups = result.unique().scalars().all()
    await log.adebug("group.listed", number_of_groups=len(groups))
    return groups


async def read_by_id(
    group_id: UUID,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> Group:
    """
    Read a group by its ID.

    Parameters
    ----------
    group_id: UUID
        The ID of the group to read.
    conn: AsyncSession
        The database session.
    log: FilteringBoundLogger
        Logger instance.

    Raises
    ------
    GroupNotFound
        If the group does not exist.
    """
    log = log.bind(group_id=group_id)
    result = await conn.execute(select(Group).where(Group.group_id == group_id))
    group = result.unique().scalar_one_or_none()
    if not group:
        await log.ainfo("group.not_found")
        raise GroupNotFound(f"Group with id {group_id} not found")
    await log.adebug("group.found")
    return group


async def read_by_name(
    group_name: str,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> Group:
    """
    Read a group by its name.

    Parameters
    ----------
    group_name: str
        The name of the group to read.
    conn: AsyncSession
        The database session.
    log: FilteringBoundLogger
        Logger instance.

    Raises
    ------
    GroupNotFound
        If the group does not exist.
    """
    group_name = group_name.strip().lower().replace(" ", "_")
    log = log.bind(group_name=group_name)
    result = await conn.execute(select(Group).where(Group.group_name == group_name))
    group = result.unique().scalar_one_or_none()
    if not group:
        await log.ainfo("group.not_found")
        raise GroupNotFound(f"Group with name {group_name} not found")
    await log.adebug("group.found")
    return group


async def add_member_by_name(
    group_name: str,
    user_id: UUID,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> Group:
    """
    Add a user to a group by group name.

    Parameters
    ----------
    group_name: str
        The name of the group.
    user_id: UUID
        The ID of the user to add.
    conn: AsyncSession
        The database session.
    log: FilteringBoundLogger
        Logger instance.

    Raises
    ------
    GroupNotFound
        If the group does not exist.
    user_service.UserNotFound
        If the user does not exist.
    """
    group_name = group_name.strip().lower().replace(" ", "_")
    log = log.bind(group_name=group_name, user_id=user_id)
    group = await read_by_name(group_name, conn, log)
    return await add_member(group.group_id, user_id, conn, log)


async def add_member(
    group_id: UUID,
    user_id: UUID,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> Group:
    """
    Add a user to a group.

    Parameters
    ----------
    group_id: UUID
        The ID of the group.
    user_id: UUID
        The ID of the user to add.
    conn: AsyncSession
        The database session.
    log: FilteringBoundLogger
        Logger instance.

    Raises
    ------
    GroupNotFound
        If the group does not exist.
    user_service.UserNotFound
        If the user does not exist.
    """
    log = log.bind(group_id=group_id, user_id=user_id)
    group = await read_by_id(group_id, conn, log)
    user = await user_service.read_by_id(user_id=user_id, conn=conn)
    if user not in group.members:
        group.members.append(user)
        await conn.flush()
        await log.ainfo("group.user_added")
    else:
        await log.ainfo("group.user_already_member")
    return group


async def remove_member_by_name(
    group_name: str,
    user_id: UUID,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> Group:
    """
    Remove a user from a group by group name.

    Parameters
    ----------
    group_name: str
        The name of the group.
    user_id: UUID
        The ID of the user to remove.
    conn: AsyncSession
        The database session.
    log: FilteringBoundLogger
        Logger instance.

    Raises
    ------
    GroupNotFound
        If the group does not exist.
    user_service.UserNotFound
        If the user does not exist.
    """
    group_name = group_name.strip().lower().replace(" ", "_")
    log = log.bind(group_name=group_name, user_id=user_id)
    group = await read_by_name(group_name, conn, log)
    return await remove_member(group.group_id, user_id, conn, log)


async def remove_member(
    group_id: UUID,
    user_id: UUID,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> Group:
    """
    Remove a user from a group.

    Parameters
    ----------
    group_id: UUID
        The ID of the group.
    user_id: UUID
        The ID of the user to remove.
    conn: AsyncSession
        The database session.
    log: FilteringBoundLogger
        Logger instance.

    Raises
    ------
    GroupNotFound
        If the group does not exist.
    user_service.UserNotFound
        If the user does not exist.
    """
    log = log.bind(group_id=group_id, user_id=user_id)
    group = await read_by_id(group_id, conn, log)
    user = await user_service.read_by_id(user_id=user_id, conn=conn)
    if user in group.members:
        group.members.remove(user)
        await conn.flush()
        await log.ainfo("group.user_removed")
    else:
        await log.ainfo("group.user_not_member")
    return group


async def delete_group(
    group_id: UUID,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> None:
    """
    Delete a group by its ID.

    Parameters
    ----------
    group_id: UUID
        The ID of the group to delete.
    conn: AsyncSession
        The database session.
    log: FilteringBoundLogger
        Logger instance.

    Raises
    ------
    GroupNotFound
        If the group does not exist.
    """
    log = log.bind(group_id=group_id)
    await conn.execute(delete(Group).where(Group.group_id == group_id))
    await log.ainfo("group.deleted")


async def add_grant(
    group_name: str,
    grant: str,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> Group:
    """
    Add a grant to a group.

    Parameters
    ----------
    group_name: str
        The name of the group.
    grant: str
        The grant to add.
    conn: AsyncSession
        The database session.
    log: FilteringBoundLogger
        Logger instance.

    Raises
    ------
    GroupNotFound
        If the group does not exist.
    """
    log = log.bind(group_name=group_name, grant=grant)
    group = await read_by_name(group_name, conn, log)
    group.add_grant(grant)
    await conn.flush()
    await log.ainfo("group.grant_added")
    return group


async def remove_grant(
    group_name: str,
    grant: str,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> Group:
    """
    Remove a grant from a group.

    Parameters
    ----------
    group_name: str
        The name of the group.
    grant: str
        The grant to remove.
    conn: AsyncSession
        The database session.
    log: FilteringBoundLogger
        Logger instance.

    Raises
    ------
    GroupNotFound
        If the group does not exist.
    """
    log = log.bind(group_name=group_name, grant=grant)
    group = await read_by_name(group_name, conn, log)
    group.remove_grant(grant)
    await conn.flush()
    await log.ainfo("group.grant_removed")
    return group
