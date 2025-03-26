"""
ORM for authentication data
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class RefreshKey(SQLModel):
    uid: int = Field(primary_key=True)

    user_id: int = Field()  # Foreign key into users table
    app_id: int = Field()  # Foreign key into app table

    # Hashed
    content: str

    last_used: datetime
    used: int
    revoked: bool
    previous: int | None = Field()  # Foreign key into this table

    created_by: int = Field()  # Link to users
    created_at: datetime
    expires_at: datetime
