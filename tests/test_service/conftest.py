"""
Configuration variables and fixtures for the service layer tests.
"""

import pytest
import pytest_asyncio
from soauth.config.settings import Settings
import structlog

@pytest_asyncio.fixture(scope="session")
def session_manager(server_settings: Settings, database):
    yield server_settings.async_manager()

@pytest_asyncio.fixture(scope="session")
def logger():
    yield structlog.get_logger()
