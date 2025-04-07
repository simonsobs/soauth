"""
Dependencies used by the API.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from soauth.config.settings import Settings

SETTINGS = Settings()
DATABASE_MANAGER = SETTINGS.async_manager()

SettingsDependency = Annotated[Settings, Depends(SETTINGS)]
DatabaseDependency = Annotated[AsyncSession, Depends(DATABASE_MANAGER.session)]
