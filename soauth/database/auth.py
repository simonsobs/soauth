"""
ORM for authentication data
"""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class RefreshKey(SQLModel):
    refresh_key_id: uuid.uuid7 = Field(primary_key=True, default_factory=uuid.uuid7)

    user_id: int = Field()  # Foreign key into users table
    app_id: int = Field()  # Foreign key into app table

    hash_algorithm: str
    hashed_content: str

    last_used: datetime
    used: int
    revoked: bool
    previous: int | None = Field()  # Foreign key into this table

    created_by: int = Field()  # Link to users
    created_at: datetime
    expires_at: datetime
