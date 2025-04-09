"""
ORM for authentication data
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from soauth.core.uuid import UUID, uuid7


class RefreshKey(SQLModel, table=True):
    refresh_key_id: UUID = Field(primary_key=True, default_factory=uuid7)

    user_id: UUID = Field(foreign_key="user.user_id", ondelete="CASCADE")
    app_id: UUID = Field(foreign_key="app.app_id", ondelete="CASCADE")

    hash_algorithm: str
    hashed_content: str

    last_used: datetime
    used: int
    revoked: bool
    previous: Optional[UUID] = Field(
        foreign_key="refreshkey.refresh_key_id", default=None
    )

    created_at: datetime
    expires_at: datetime
