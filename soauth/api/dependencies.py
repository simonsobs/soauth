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
from soauth.service.github import GithubAuthProvider
from soauth.service.provider import AuthProvider


@lru_cache
def SETTINGS():
    settings = Settings()

    from .setup import example_setup

    for key, value in example_setup(settings=settings).items():
        setattr(settings, key, value)

    return settings


DATABASE_MANAGER = SETTINGS().async_manager()


async def get_async_session():
    async with DATABASE_MANAGER.session() as session:
        async with session.begin():
            yield session


def logger():
    return get_logger()


@lru_cache
def get_github():
    return GithubAuthProvider()


SettingsDependency = Annotated[Settings, Depends(SETTINGS)]
DatabaseDependency = Annotated[AsyncSession, Depends(get_async_session)]
LoggerDependency = Annotated[FilteringBoundLogger, Depends(logger)]
AuthProviderDependency = Annotated[AuthProvider, Depends(get_github)]
