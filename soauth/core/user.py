"""
A shared user object that is serialized.
"""

from soauth.core.uuid import uuid7, UUID

import pydantic


class UserData(pydantic.BaseModel):
    user_id: UUID
    user_name: str
    email: str
    grants: set[str]
    groups: set[str]
