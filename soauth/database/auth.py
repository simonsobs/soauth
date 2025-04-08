"""
ORM for authentication data
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from soauth.core.uuid import UUID, uuid7


class RefreshKey(SQLModel, table=True):
    refresh_key_id: UUID = Field(primary_key=True, default_factory=uuid7)

    user_id: UUID = Field(
        foreign_key="user.user_id", ondelete="CASCADE"
    )  # Foreign key into users table
    app_id: UUID = Field(
        foreign_key="app.app_id", ondelete="CASCADE"
    )  # Foreign key into app table

    hash_algorithm: str
    hashed_content: str

    last_used: datetime
    used: int
    revoked: bool
    previous: Optional[UUID] = Field(
        foreign_key="refreshkey.refresh_key_id", default=None
    )  # Foreign key into this table

    created_at: datetime
    expires_at: datetime
