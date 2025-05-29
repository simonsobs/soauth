"""
A shared user object that is serialized.
"""

from pydantic import BaseModel

from soauth.core.uuid import UUID


class UserData(BaseModel):
    user_id: UUID
    user_name: str
    full_name: str | None
    email: str | None
    grants: set[str] | None
    groups: set[str] | None
