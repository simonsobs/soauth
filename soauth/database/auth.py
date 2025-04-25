"""
ORM for authentication data
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

from soauth.core.uuid import UUID, uuid7
from soauth.database.app import App
from soauth.database.user import User


class RefreshKey(SQLModel, table=True):
    refresh_key_id: UUID = Field(primary_key=True, default_factory=uuid7)

    user_id: UUID = Field(foreign_key="user.user_id", ondelete="CASCADE")
    app_id: UUID = Field(foreign_key="app.app_id", ondelete="CASCADE")

    user: User = Relationship()
    app: App = Relationship()

    hash_algorithm: str
    hashed_content: str

    # Whether this is an API key (True) or a regular login token (False)
    api_key: bool

    last_used: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    used: int
    revoked: bool
    previous: Optional[UUID] = Field(
        foreign_key="refreshkey.refresh_key_id", default=None
    )

    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))
