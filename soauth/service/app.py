"""
Service layer for creating applications.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from soauth.config.settings import Settings
from soauth.core.cryptography import generate_key_pair
from soauth.core.uuid import UUID
from soauth.database.app import App
from soauth.database.user import User


class AppNotFound(Exception):
    pass


async def create(
    domain: str,
    user: User,
    settings: Settings,
    conn: AsyncSession,
    log: FilteringBoundLogger,
) -> App:
    log = log.bind(
        user_id=user.user_id, domain=domain, key_pair_type=settings.key_pair_type
    )

    public_key, private_key = generate_key_pair(
        key_pair_type=settings.key_pair_type, key_password=settings.key_password
    )

    app = App(
        created_by_user_id=user.user_id,
        created_by=user,
        created_at=datetime.now(timezone.utc),
        domain=domain,
        key_pair_type=settings.key_pair_type,
        public_key=public_key,
        private_key=private_key,
    )

    conn.add(app)

    log = log.bind(app_id=app.app_id)
    await log.ainfo("app.created")

    return app


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
