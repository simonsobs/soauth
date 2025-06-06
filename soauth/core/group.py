"""
Core group data models.
"""

from datetime import datetime

from pydantic import BaseModel

from soauth.core.uuid import UUID

from .user import UserData


class GroupData(BaseModel):
    group_id: UUID
    group_name: str
    created_by: UserData
    created_at: datetime
    grants: set[str] | None
    members: list[UserData]
