"""
Dependencies used by the API.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger
from structlog.typing import FilteringBoundLogger

from soauth.config.settings import Settings


@lru_cache
def SETTINGS():
    settings = Settings()

    if settings.create_example_app_and_user:
        import datetime

        from soauth.core.cryptography import generate_key_pair
        from soauth.database.app import App
        from soauth.database.group import Group
        from soauth.database.meta import ALL_TABLES
        from soauth.database.user import User

        ALL_TABLES[1]

        manager = settings.sync_manager()

        manager.create_all()

        with manager.session() as conn:
            user = User(
                full_name="Example User",
                user_name="example_user",
                email="no@email",
                grants="admin",
            )

            group = Group(
                group_name="example_user",
                created_by_user_id=user.user_id,
                created_by=user,
                created_at=datetime.datetime.now(datetime.timezone.utc),
                members=[user],
            )

            public, private = generate_key_pair(
                key_pair_type=settings.key_pair_type, key_password=settings.key_password
            )
            app = App(
                created_by_user_id=user.user_id,
                created_by=user,
                created_at=datetime.datetime.now(datetime.timezone.utc),
                domain="http://localhost:8001",
                key_pair_type=settings.key_pair_type,
                public_key=public,
                private_key=private,
                redirect_url="http://localhost:8001/redirect",
            )

            conn.add_all([user, group, app])

            for admin_user in settings.create_admin_users:
                new_user = User(
                    user_name=admin_user, grants="admin", full_name="TBD", email="TBD"
                )
                new_group = Group(
                    group_name=admin_user,
                    created_by_user_id=new_user.user_id,
                    created_by=new_user,
                    created_at=datetime.datetime.now(datetime.timezone.utc),
                    members=[new_user],
                )
                conn.add_all([new_user, new_group])

            second_demo_app = App(
                created_by_user_id=user.user_id,
                created_by=user,
                created_at=datetime.datetime.now(datetime.timezone.utc),
                domain="http://simonsobs.org",
                key_pair_type=settings.key_pair_type,
                public_key=public,
                private_key=private,
                redirect_url="http://simonsobs.org/redirect",
            )

            conn.add(second_demo_app)

            conn.commit()
            print(f"Created example, app_id: {app.app_id}")
            settings.created_app_id = app.app_id
            settings.created_app_public_key = app.public_key
            settings.created_app_client_secret = app.client_secret

    return settings


DATABASE_MANAGER = SETTINGS().async_manager()


async def get_async_session():
    async with DATABASE_MANAGER.session() as session:
        async with session.begin():
            yield session


def logger():
    return get_logger()


SettingsDependency = Annotated[Settings, Depends(SETTINGS)]
DatabaseDependency = Annotated[AsyncSession, Depends(get_async_session)]
LoggerDependency = Annotated[FilteringBoundLogger, Depends(logger)]
