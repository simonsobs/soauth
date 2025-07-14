"""
Service layer for users
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from soauth.core.user import UserData
from soauth.core.uuid import UUID
from soauth.database.group import Group
from soauth.database.user import User


class UserNotFound(Exception):
    pass


class UserExistsError(Exception):
    pass


async def create(
    user_name: str,
    email: str,
    full_name: str,
    profile_image: str | None,
    grants: str,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> User:
    """
    Creates a user, if they do not exist.
    """

    user_name = user_name.strip().lower().replace(" ", "_")

    log = log.bind(user_name=user_name, email=email, grants=grants)

    current_time = datetime.now(timezone.utc)

    try:
        user = User(
            user_name=user_name,
            email=email,
            grants=grants,
            full_name=full_name,
            gh_profile_image_url=profile_image,
        )
    except IntegrityError:
        await log.ainfo("user.create.exists")
        raise UserExistsError(f"User with user name {user_name} already exists")

    group = Group(
        group_name=user_name,
        created_by_user_id=user.user_id,
        created_by=user,
        created_at=current_time,
        members=[user],
    )

    user.groups = [group]

    conn.add_all([user, group])

    log = log.bind(user_id=user.user_id, group_id=group.group_id)
    await log.ainfo("user.created")

    return user


async def read_by_id(user_id: UUID, conn: AsyncSession) -> User:
    res = await conn.get(User, user_id)

    if res is None:
        raise UserNotFound(f"User with ID {user_id} not found in the database")

    return res


async def read_by_name(user_name: str, conn: AsyncSession) -> User:
    user_name = user_name.strip().lower().replace(" ", "_")

    query = select(User).filter(User.user_name == user_name)
    res = (await conn.execute(query)).unique().scalar_one_or_none()

    if res is None:
        raise UserNotFound(f"User with name {user_name} not found in the database")

    return res


async def get_user_list(conn: AsyncSession) -> list[UserData]:
    """
    Get a list of all users registered to the system.
    """
    query = select(User)
    res = (await conn.execute(query)).unique().scalars().all()
    return [u.to_core() for u in res]


async def add_grant(
    user_name: str, grant: str, conn: AsyncSession, log: FilteringBoundLogger
) -> User:
    user_name = user_name.strip().lower().replace(" ", "_")

    log = log.bind(user_name=user_name, grant=grant)
    user = await read_by_name(user_name=user_name, conn=conn)
    log = log.bind(user_id=user.user_id)

    user.add_grant(grant=grant)
    conn.add(user)

    await log.ainfo("user.grant_added")

    return user


async def remove_grant(
    user_name: str, grant: str, conn: AsyncSession, log: FilteringBoundLogger
) -> User:
    user_name = user_name.strip().lower().replace(" ", "_")

    log = log.bind(user_name=user_name, grant=grant)
    user = await read_by_name(user_name=user_name, conn=conn)
    log = log.bind(user_id=user.user_id)

    user.remove_grant(grant=grant)
    conn.add(user)

    await log.ainfo("user.grant_removed")

    return user


async def delete(user_name: str, conn: AsyncSession, log: FilteringBoundLogger):
    """
    Deletes both the 'User' and 'Group' model.
    """
    user_name = user_name.strip().lower().replace(" ", "_")

    user = await read_by_name(user_name=user_name, conn=conn)
    group = (
        (await conn.execute(select(Group).filter(Group.group_name == user_name)))
        .unique()
        .scalar_one_or_none()
    )

    log = log.bind(user_id=user.user_id)

    if group is not None:
        log = log.bind(group_id=group.group_id)
    else:
        log = log.bind(group_id=None)

    with conn.no_autoflush:
        await conn.delete(user)
        if group is not None:
            await conn.delete(group)

    await log.ainfo("user.deleted")

    return
