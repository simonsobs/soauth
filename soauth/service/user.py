"""
Service layer for users
"""

from datetime import datetime

from sqlalchemy import select, delete as db_delete
from sqlalchemy.ext.asyncio import AsyncSession
from soauth.config.managers import AsyncSessionManager

from soauth.database.group import Group, GroupMembership
from soauth.database.user import User

from structlog import BoundLogger
from soauth.core.uuid import uuid7, UUID


class UserNotFound(Exception):
    pass


async def create(
    user_name: str, email: str, full_name: str, grants: str, conn: AsyncSession, log: BoundLogger
) -> User:
    """
    Creates a user, if they do not exist.
    """

    log = log.bind(username=user_name, email=email, grants=grants)

    current_time = datetime.now()

    user = User(user_name=user_name, email=email, grants=grants, full_name=full_name)

    group = Group(
        group_name=user_name,
        created_by_user_id=user.user_id,
        created_by=user,
        created_at=current_time,
    )

    member = GroupMembership(
        user_id=user.user_id,
        group_id=group.group_id,
        created_at=current_time
    )

    conn.add_all([user, group, member])

    log = log.bind(user_id=user.user_id, group_id=group.group_id)
    await log.ainfo("user.created")

    return user


async def read_by_id(user_id: UUID, conn: AsyncSession) -> User:
    res = await conn.get(User, user_id)

    if res is None:
        raise UserNotFound(f"User with ID {user_id} not found in the database")

    return res


async def read_by_name(user_name: str, conn: AsyncSession) -> User:
    query = select(User).filter(User.user_name == user_name)
    res = (await conn.execute(query)).scalar_one_or_none()

    if res is None:
        raise UserNotFound(f"User with name {user_name} not found in the database")

    return res


async def add_grant(user_name: str, grant: str, conn: AsyncSession, log: BoundLogger) -> User:
    log = log.bind(username=user_name, grant=grant)
    user = await read_by_name(user_name=user_name, conn=conn)
    log = log.bind(user_id=user.user_id)

    user.add_grant(grant=grant)
    conn.add(user)

    await log.ainfo("user.grant_added")

    return user


async def remove_grant(user_name: str, grant: str, conn: AsyncSession, log: BoundLogger) -> User:
    log = log.bind(username=user_name, grant=grant)
    user = await read_by_name(user_name=user_name, conn=conn)
    log = log.bind(user_id=user.user_id)

    user.remove_grant(grant=grant)
    conn.add(user)

    await log.ainfo("user.grant_removed")

    return user


async def delete(user_name: str, conn: AsyncSession, log: BoundLogger):
    """
    Deletes both the 'User' and 'Group' model.
    """

    user = await read_by_name(user_name=user_name, conn=conn)
    group = (
        await conn.execute(select(Group).filter(Group.group_name == user_name))
    ).scalar_one_or_none()

    log = log.bind(user_id=user.user_id, group_id=group.group_id)

    with conn.no_autoflush:
        await conn.delete(user)
        await conn.delete(group)

    await log.ainfo("user.deleted")

    return
