"""
Group ORM
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from soauth.core.uuid import UUID, uuid7

if TYPE_CHECKING:
    from .user import User


class Group(SQLModel, table=True):
    group_id: UUID = Field(primary_key=True, default_factory=uuid7)

    group_name: str = Field(unique=True)
    created_by_user_id: UUID = Field(foreign_key="user.user_id")
    created_by: "User" = Relationship()
    created_at: datetime

    members: list["GroupMembership"] = Relationship(
        back_populates="group", cascade_delete=True
    )


class GroupMembership(SQLModel, table=True):
    """
    A record of a user's group membership.
    """

    # A composite primary key of these two is pretty much it.
    user_id: UUID = Field(
        primary_key=True, foreign_key="user.user_id"
    )  # Foreign key into Users table
    group_id: UUID = Field(
        primary_key=True, foreign_key="group.group_id"
    )  # Foreign key into Group table

    user: "User" = Relationship(back_populates="groups")
    group: "Group" = Relationship(back_populates="members")

    created_at: datetime
