"""
A shared user object that is serialized.
"""

import pydantic

from soauth.core.uuid import UUID


class UserData(pydantic.BaseModel):
    user_id: UUID
    user_name: str
    email: str
    grants: set[str]
    groups: set[str]
