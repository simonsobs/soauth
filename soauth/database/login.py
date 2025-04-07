"""
Login request tracking.
"""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class LoginRequest(SQLModel):
    login_request_id: uuid.uuid7 = Field(primary_key=True, default_factory=uuid.uuid7)

    app_id: uuid.uuid7  # Foreign key
    user_id: uuid.uuid7 | None = None  # Foreign key

    redirect_to: str | None = None

    initiated_at: datetime
    completed_at: datetime | None = None

    stale: bool = False
