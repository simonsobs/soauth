"""
A shared user object that is serialized.
"""

import pydantic

from soauth.core.uuid import UUID


class UserData(pydantic.BaseModel):
    user_id: UUID
    user_name: str
    full_name: str | None
    email: str | None
    grants: set[str]
    groups: set[str]
