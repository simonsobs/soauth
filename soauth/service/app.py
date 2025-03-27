"""
Service layer for creating applications.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from soauth.config.settings import Settings
from soauth.core.cryptography import generate_key_pair
from soauth.database.app import App
from soauth.database.user import User


class AppNotFound(Exception):
    pass


async def create(
    domain: str, user: User, settings: Settings, conn: AsyncSession
) -> App:
    public_key, private_key = generate_key_pair(
        key_pair_type=settings.key_pair_type, key_password=settings.key_password
    )

    app = App(
        created_by=user.uid,
        created_at=datetime.now(),
        domain=domain,
        key_pair_type=settings.signing_method,
        public_key=public_key,
        private_key=private_key,
    )

    conn.add(app)
    await conn.commit()
    await conn.refresh(app)

    return app


async def read_by_id(uid: int, conn: AsyncSession) -> App:
    res = await conn.get(App, uid)

    if res is None:
        raise AppNotFound

    return res


async def refresh_keys(uid: int, settings: Settings, conn: AsyncSession) -> App:
    app = await read_by_id(uid=uid, conn=conn)

    public_key, private_key = generate_key_pair(
        key_pair_type=settings.key_pair_type,
        key_password=settings.key_password,
    )

    app.key_pair_type = settings.key_pair_type
    app.public_key = public_key
    app.private_key = private_key

    conn.add(app)
    await conn.commit()
    await conn.refresh(app)

    return app


async def delete(uid: int, conn: AsyncSession) -> None:
    app = await read_by_id(uid=uid, conn=conn)

    await conn.delete(app)
    await conn.commit()

    return
