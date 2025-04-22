"""
The mock Auth Provider, used for testing.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from soauth.config.settings import Settings
from soauth.database.login import LoginRequest
from soauth.database.user import User
from soauth.service import user as user_service
from soauth.service.provider import AuthProvider, BaseLoginError


class MockLoginError(BaseLoginError):
    pass


class MockProvider(AuthProvider):
    name = "mock"

    user_name: str
    full_name: str
    email: str
    grants: str

    def __init__(self, user_name: str, full_name: str, email: str, grants: str):
        self.user_name = user_name
        self.full_name = full_name
        self.email = email
        self.grants = grants

    async def redirect(self, login_request: LoginRequest, settings: Settings) -> str:
        # Does not make sense for the mock provider
        raise NotImplementedError

    async def login(
        self,
        code: str,
        settings: Settings,
        conn: AsyncSession,
        log: FilteringBoundLogger,
    ) -> User:
        try:
            user = await user_service.read_by_name(user_name=self.user_name, conn=conn)
        except user_service.UserNotFound:
            user = await user_service.create_user(
                user_name=self.user_name,
                email=self.email,
                full_name=self.full_name,
                grants=self.grants,
                conn=conn,
                log=log,
            )

        conn.add(user)

        return user

    async def refresh(
        self,
        user: User,
        settings: Settings,
        conn: AsyncSession,
        log: FilteringBoundLogger,
    ) -> User:
        user.full_name = self.full_name
        user.email = self.email
        user.grants = self.grants

        conn.add(user)

        return user
