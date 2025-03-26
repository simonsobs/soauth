"""
A shared user object that is serialized.
"""

import pydantic


class UserData(pydantic.BaseModel):
    uid: int
    username: str
    email: str
    grants: set[str]
    groups: set[str]
