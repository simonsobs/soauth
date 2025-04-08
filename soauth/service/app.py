"""
Service layer for creating applications.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import BoundLogger

from soauth.config.settings import Settings
from soauth.core.cryptography import generate_key_pair
from soauth.database.app import App
from soauth.database.user import User
from soauth.core.uuid import uuid7, UUID


class AppNotFound(Exception):
    pass


async def create(
    domain: str, user: User, settings: Settings, conn: AsyncSession, log: BoundLogger
) -> App:
    log.bind(user=user.user_id, domain=domain, key_pair_type=settings.key_pair_type)
    
    public_key, private_key = generate_key_pair(
        key_pair_type=settings.key_pair_type, key_password=settings.key_password
    )

    app = App(
        created_by=user.user_id,
        created_at=datetime.now(),
        domain=domain,
        key_pair_type=settings.key_pair_type,
        public_key=public_key,
        private_key=private_key,
    )

    conn.add(app)
    await conn.commit()
    await conn.refresh(app)

    log.bind(app_id=app.app_id)
    await log.ainfo("app.created")

    return app


async def read_by_id(app_id: UUID, conn: AsyncSession) -> App:
    res = await conn.get(App, app_id)

    if res is None:
        raise AppNotFound

    return res


async def refresh_keys(app_id: UUID, settings: Settings, conn: AsyncSession, log: BoundLogger) -> App:
    log.bind(app_id=app_id, key_paid_type=settings.key_pair_type)
    app = await read_by_id(app_id=app_id, conn=conn)

    public_key, private_key = generate_key_pair(
        key_pair_type=settings.key_pair_type,
        key_password=settings.key_password,
    )

    app.public_key = public_key
    app.private_key = private_key

    conn.add(app)
    await conn.commit()
    await conn.refresh(app)
    
    await log.ainfo("app.key_refreshed")

    return app


async def delete(app_id: UUID, conn: AsyncSession, log: BoundLogger) -> None:
    log.bind(app_id=app_id)
    app = await read_by_id(app_id=app_id, conn=conn)
    log.bind(created_by=app.created_by, created_at=app.created_at, domain=app.domain)

    await conn.delete(app)
    await conn.commit()

    await log.ainfo("app.deleted")

    return
