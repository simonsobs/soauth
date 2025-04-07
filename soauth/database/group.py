"""
Group ORM
"""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class Group(SQLModel):
    group_id: uuid.uuid7 = Field(primary_key=True, default_factory=uuid.uuid7)

    name: str = Field(unique=True)
    created_by: int  # Foreign key into users table
    created_at: datetime


class GroupMembership(SQLModel):
    """
    A record of a user's group membership.
    """

    # A composite primary key of these two is pretty much it.
    user_id = Field(primary_key=True)  # Foreign key into Users table
    group_id = Field(primary_key=True)  # Foreign key into Group table

    created_at: datetime
