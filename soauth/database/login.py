"""
Login request tracking.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel

from soauth.core.uuid import UUID, uuid7


class LoginRequest(SQLModel, table=True):
    login_request_id: UUID = Field(primary_key=True, default_factory=uuid7)

    app_id: UUID  # Foreign key
    user_id: UUID | None = None  # Foreign key

    redirect_to: str | None = None

    initiated_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    completed_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )

    stale: bool = False
