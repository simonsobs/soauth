"""
Core configuration
"""

import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from soauth.config.settings import Settings


@pytest_asyncio.fixture(scope="session")
def database_container():
    with PostgresContainer() as container:
        yield {
            "database_type": "postgres",
            "database_user": container.username,
            "database_password": container.password,
            "database_port": container.get_exposed_port(container.port),
            "database_host": "localhost",
            "database_db": container.dbname,
            "database_echo": True,
        }


@pytest_asyncio.fixture(scope="session")
def server_settings(database_container):
    yield Settings(
        **database_container,
        github_client_id="NONE",
        github_client_secret="NONE",
        github_redirect_uri="NONE",
        github_organization_checks=["NONE"],
    )


@pytest_asyncio.fixture(scope="session")
def database(server_settings: Settings):
    server_settings.sync_manager().create_all()
