"""
Shared app model
"""

from datetime import datetime

from pydantic import BaseModel

from .uuid import UUID


class AppData(BaseModel):
    app_id: UUID
    created_by_user_id: UUID | None
    created_by_user_name: str | None
    created_at: datetime
    domain: str


class LoggedInUserData(BaseModel):
    user_name: str
    user_id: UUID
    app_id: UUID
    refresh_key_id: UUID
    first_authenticated: datetime
    last_authenticated: datetime
    login_expires: datetime
