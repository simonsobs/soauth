"""
A shared user object that is serialized.
"""

import uuid

import pydantic


class UserData(pydantic.BaseModel):
    user_id: uuid.uuid7
    username: str
    email: str
    grants: set[str]
    groups: set[str]
