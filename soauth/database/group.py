"""
Group ORM
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

from soauth.core.uuid import UUID, uuid7

if TYPE_CHECKING:
    from .user import User


class GroupMembership(SQLModel, table=True):
    """
    A record of a user's group membership.
    """

    user_id: Optional[UUID] = Field(primary_key=True, foreign_key="user.user_id")
    group_id: Optional[UUID] = Field(primary_key=True, foreign_key="group.group_id")


class Group(SQLModel, table=True):
    group_id: UUID = Field(primary_key=True, default_factory=uuid7)

    group_name: str = Field(unique=True)
    created_by_user_id: UUID = Field(foreign_key="user.user_id")
    created_by: "User" = Relationship()
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))

    members: list["User"] = Relationship(
        back_populates="groups",
        link_model=GroupMembership,
    )
