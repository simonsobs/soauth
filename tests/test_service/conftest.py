"""
Configuration variables and fixtures for the service layer tests.
"""

import pytest_asyncio
import structlog

from soauth.config.settings import Settings
from soauth.service import app as app_service
from soauth.service import user as user_service
from soauth.service.mock import MockProvider


@pytest_asyncio.fixture(scope="session")
def session_manager(server_settings: Settings, database):
    yield server_settings.async_manager()


@pytest_asyncio.fixture(scope="session")
def logger():
    yield structlog.get_logger()


@pytest_asyncio.fixture(scope="session")
async def user(session_manager, logger):
    async with session_manager.session() as conn:
        async with conn.begin():
            user = await user_service.create(
                user_name="admin",
                email="admin@simonsobservatory.org",
                full_name="Admin User",
                grants="admin",
                conn=conn,
                log=logger,
            )

            USER_ID = user.user_id

    yield USER_ID

    async with session_manager.session() as conn:
        async with conn.begin():
            await user_service.delete(
                user_name="admin",
                conn=conn,
                log=logger,
            )


@pytest_asyncio.fixture(scope="session")
async def app(session_manager, logger, user, server_settings):
    async with session_manager.session() as conn:
        async with conn.begin():
            app = await app_service.create(
                name="Simons Observatory",
                api_access=False,
                domain="https://simonsobs.org",
                redirect_url="https://simonsobs.org/callback",
                user=await user_service.read_by_id(user_id=user, conn=conn),
                settings=server_settings,
                conn=conn,
                log=logger,
            )

            APP_ID = app.app_id

    yield APP_ID

    async with session_manager.session() as conn:
        async with conn.begin():
            await app_service.delete(
                app_id=APP_ID,
                conn=conn,
                log=logger,
            )


@pytest_asyncio.fixture(scope="session")
async def provider():
    # Same as `user`
    yield MockProvider(
        user_name="admin",
        email="admin@simonsobservatory.org",
        full_name="Admin User",
        grants="admin",
    )
