"""
Core client, including session management.
"""

from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, create_engine


class SyncSessionManager:
    """
    A manager for asynchronous sessions. Expected usage of this class to interact:

    manager = SyncSessionManager(conn_url)

    with manager.session() as conn:
        source_1 = conn.get(SourceTable, 1)
    """

    connection_url: str
    engine: Engine
    session: sessionmaker

    def __init__(self, connection_url: str, echo: bool = False):
        self.connection_url = connection_url
        self.engine = create_engine(self.connection_url, echo=echo)
        self.session = sessionmaker(self.engine)

    def create_all(self):
        """
        Run the `SQLModel.metadata.create_all` migration tool. Required
        to set up the table schema.
        """
        with self.engine.begin() as conn:
            SQLModel.metadata.create_all(conn)

    def drop_all(self):
        """
        Run the `SQLModel.metadata.drop_all` deletion method. WARNING: this
        will delete all data in your database; you probably don't want to do this
        unless you are writing a test.
        """
        with self.engine.begin() as conn:
            SQLModel.metadata.drop_all(conn)


class AsyncSessionManager:
    """
    A manager for asynchronous sessions. Expected usage of this class to interact:

    manager = SessionManager(conn_url)

    async with manager.session() as conn:
        res = await lightcurve_read_band(id=993, band_name="f220", conn=conn)
    """

    connection_url: str
    engine: AsyncEngine
    session: async_sessionmaker

    def __init__(self, connection_url: str, echo: bool = False):
        self.connection_url = connection_url
        self.engine = create_async_engine(self.connection_url, echo=echo)
        self.session = async_sessionmaker(self.engine)

    async def create_all(self):
        """
        Run the `SQLModel.metadata.create_all` migration tool. Required
        to set up the table schema.
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def drop_all(self):
        """
        Run the `SQLModel.metadata.drop_all` deletion method. WARNING: this
        will delete all data in your database; you probably don't want to do this
        unless you are writing a test.
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
