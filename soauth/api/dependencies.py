"""
Dependencies used by the API.
"""

from fastapi import Depends
from typing import Annotated

from soauth.config.settings import Settings
from sqlalchemy.ext.asyncio import AsyncSession

SETTINGS = Settings()
DATABASE_MANAGER = SETTINGS.async_manager()

SettingsDependency = Annotated[Settings, Depends(SETTINGS)]
DatabaseDependency = Annotated[AsyncSession, Depends(DATABASE_MANAGER.session)]