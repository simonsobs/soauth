"""
Main settings object.
"""

from datetime import timedelta
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from soauth.core.uuid import UUID

from .managers import AsyncSessionManager, SyncSessionManager


class Settings(BaseSettings):
    database_type: Literal["sqlite", "postgres"] = "sqlite"
    database_user: str | None = None
    database_password: str | None = None
    database_port: int | None = None
    database_host: str | None = None
    database_db: str = "soauth.db"

    database_echo: bool = False

    # Example/testing setup
    create_example_app_and_user: bool = False
    created_app_public_key: str | bytes | None = None
    created_app_client_secret: str | None = None
    create_admin_users: list[str] = []
    created_app_id: UUID | None = None
    host_development_only_endpoint: bool = False

    key_pair_type: str = "Ed25519"
    key_password: str = "CHANGEME"
    hash_algorithm: str = "xxh3"

    refresh_key_expiry: timedelta = timedelta(weeks=26)
    access_key_expiry: timedelta = timedelta(hours=8)

    stale_login_expiry: timedelta = timedelta(minutes=30)
    login_record_length: timedelta = timedelta(weeks=2)

    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_redirect_uri: str | None = None
    github_organization_checks: list[str] = []

    # Production setup
    hostname: str = "http://localhost:8000"
    management_hostname: str = "http://localhost:8001"
    management_path: str = "/management"

    # If create_files is set, we automatically create the 'default' app and
    # write out that data if the files do not already exist.
    create_files: bool = False  # Create the files if they don't exist
    initial_admin: str | None = (
        None  # Create an initial adiminstrator account (github username)
    )
    app_id_filename: Path | None = None  # Suggest /data/app_id
    client_secret_filename: Path | None = None  # Suggest /data/client_secret
    public_key_filename: Path | None = None  # Suggest /data/public_key.pem

    model_config = SettingsConfigDict(env_prefix="SOAUTH_", env_file=".env")

    @property
    def sync_driver(self) -> str:
        match self.database_type:
            case "sqlite":
                return "sqlite"
            case "postgres":
                return "postgresql+psycopg"
            case _:
                raise ValueError

    @property
    def async_driver(self) -> str:
        match self.database_type:
            case "sqlite":
                return "aiosqlite"
            case "postgres":
                return "postgresql+asyncpg"
            case _:
                raise ValueError

    @property
    def sync_uri(self) -> URL:
        return URL.create(
            drivername=self.sync_driver,
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_db,
        )

    def sync_manager(self) -> SyncSessionManager:
        return SyncSessionManager(connection_url=self.sync_uri, echo=self.database_echo)

    @property
    def async_uri(self) -> URL:
        return URL.create(
            drivername=self.async_driver,
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_db,
        )

    def async_manager(self) -> AsyncSessionManager:
        return AsyncSessionManager(
            connection_url=self.async_uri, echo=self.database_echo
        )
