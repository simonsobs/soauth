"""
Service layer for users
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soauth.database.group import Group, GroupMembership
from soauth.database.user import User


class UserNotFound(Exception):
    pass


async def create(
    username: str, email: str, access_level: int, conn: AsyncSession
) -> User:
    """
    Creates a user, if they do not exist.
    """

    user = User(username=username, email=email, access_level=access_level)

    group = Group(
        name=username,
        # Ehhh created by is an int need to do some orm magic
        created_by=user,
        created_at=datetime.now(),
    )

    member = GroupMembership(
        user=user,
        group=group,
    )

    conn.add_all([user, group, member])
    await conn.commit()
    await conn.refresh(user)

    return user


async def read_by_id(uid: int, conn: AsyncSession) -> User:
    res = await conn.get(User, uid)

    if res is None:
        raise UserNotFound(f"User with ID {uid} not found in the database")

    return res


async def read_by_name(username: str, conn: AsyncSession) -> User:
    query = select(User).filter(User.username == username)
    res = (await conn.execute(query)).scalar_one_or_none()

    if res is None:
        raise UserNotFound(f"User with name {username} not found in the database")

    return res


async def add_grant(username: str, grant: str, conn: AsyncSession) -> User:
    user = await read_by_name(username=username, conn=conn)

    user.add_grant(grant=grant)
    conn.add(user)

    await conn.commit()
    await conn.refresh(user)

    return user


async def remove_grant(username: str, grant: str, conn: AsyncSession) -> User:
    user = await read_by_name(username=username, conn=conn)

    user.remove_grant(grant=grant)
    conn.add(user)

    await conn.commit()
    await conn.refresh(user)

    return user


async def delete(username: str, conn: AsyncSession):
    """
    Deletes both the 'User' and 'Group' model.
    """

    user = await read_by_name(username=username, conn=conn)
    group = (
        await conn.execute(select(Group).filter(Group.name == username))
    ).scalar_one_or_none()

    await conn.delete(user)
    await conn.delete(group)

    await conn.commit()

    return
