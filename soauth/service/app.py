"""
Service layer for creating applications.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from soauth.config.settings import Settings
from soauth.core.app import AppData
from soauth.core.cryptography import generate_key_pair
from soauth.core.random import client_secret
from soauth.core.uuid import UUID
from soauth.database.app import App
from soauth.database.user import User
from soauth.service import user as user_service




class AppNotFound(Exception):
    pass


async def create(
    name: str,
    domain: str,
    redirect_url: str,
    visibility_grant: str,
    api_access: bool,
    user: User,
    settings: Settings,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> App:
    log = log.bind(
        user_id=user.user_id,
        domain=domain,
        visibility_grant=visibility_grant,
        key_pair_type=settings.key_pair_type,
        name=name,
        api_access=api_access,
    )

    public_key, private_key = generate_key_pair(
        key_pair_type=settings.key_pair_type, key_password=settings.key_password
    )

    app = App(
        app_name=name,
        api_access=api_access,
        created_by_user_id=user.user_id,
        created_by=user,
        created_at=datetime.now(timezone.utc),
        domain=domain,
        visibility_grant=visibility_grant,
        redirect_url=redirect_url,
        key_pair_type=settings.key_pair_type,
        public_key=public_key,
        private_key=private_key,
    )

    conn.add(app)

    log = log.bind(app_id=app.app_id)
    await log.ainfo("app.created")

    return app


async def get_app_list(
    created_by_user_id: UUID | None,
    user_name: str,
    conn: AsyncSession,
    require_api_access: bool = False,
) -> list[AppData]:
    """
    Get the app list, either all (created_by_user_id = None) or a specific
    user. If require_api_access is True, only those that have API access enabled
    are returned.
    """
    query = select(App)

    if created_by_user_id is not None:
        query = query.filter_by(created_by_user_id=created_by_user_id)

    if require_api_access:
        query = query.filter_by(api_access=True)

    res = await conn.execute(query)
    user_details = await user_service.read_by_name(user_name=user_name, conn=conn)
    return [x.to_core() for x in res.scalars().unique().all() if x.has_visibility_grant(user_details.get_effective_grants())]


async def read_by_id(app_id: UUID, conn: AsyncSession) -> App:
    res = await conn.get(App, app_id)

    if res is None:
        raise AppNotFound

    return res


async def refresh_keys(
    app_id: UUID, settings: Settings, conn: AsyncSession, log: FilteringBoundLogger
) -> App:
    log = log.bind(app_id=app_id, key_pair_type=settings.key_pair_type)
    app = await read_by_id(app_id=app_id, conn=conn)

    public_key, private_key = generate_key_pair(
        key_pair_type=settings.key_pair_type,
        key_password=settings.key_password,
    )

    app.public_key = public_key
    app.private_key = private_key
    app.client_secret = client_secret()

    conn.add(app)

    await log.ainfo("app.key_refreshed")

    return app


async def delete(app_id: UUID, conn: AsyncSession, log: FilteringBoundLogger) -> None:
    log = log.bind(app_id=app_id)
    app = await read_by_id(app_id=app_id, conn=conn)
    log = log.bind(
        created_by_user_id=app.created_by_user_id,
        created_at=app.created_at,
        domain=app.domain,
    )

    await conn.delete(app)

    await log.ainfo("app.deleted")

    return
