"""
Shared app model
"""

from datetime import datetime

from pydantic import BaseModel

from .uuid import UUID


class AppData(BaseModel):
    app_name: str
    app_id: UUID
    api_access: bool
    created_by_user_id: UUID | None
    created_by_user_name: str | None
    created_at: datetime
    domain: str
    visibility_grant: str | None = None


class LoggedInUserData(BaseModel):
    user_name: str
    user_id: UUID
    app_id: UUID
    app_name: str
    api_key: bool
    refresh_key_id: UUID
    first_authenticated: datetime
    last_authenticated: datetime
    login_expires: datetime
