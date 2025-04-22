"""
Base for providers.
"""

import abc
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from soauth.config.settings import Settings
from soauth.database.login import LoginRequest
from soauth.database.user import User


class BaseLoginError(Exception):
    pass


class AuthProvider(abc.ABC):
    """
    The base class for authentication providers. Downstream must implement:

    - redirect: get the URL to redirect users to for authentication against
                the main service.
    - login: use the provided code through the OAuth mechanism to find or
             create the user.
    - refresh: refresh the user via the central auth provider.
    """

    name: Literal["mock", "github"]

    @abc.abstractmethod
    async def redirect(self, login_request: LoginRequest, settings: Settings) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    async def login(
        self,
        code: str,
        settings: Settings,
        conn: AsyncSession,
        log: FilteringBoundLogger,
    ) -> User:
        raise NotImplementedError

    @abc.abstractmethod
    async def refresh(
        self,
        user: User,
        settings: Settings,
        conn: AsyncSession,
        log: FilteringBoundLogger,
    ) -> User:
        raise NotImplementedError
