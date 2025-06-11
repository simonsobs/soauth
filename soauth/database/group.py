"""
Group ORM
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

from soauth.core.group import GroupData
from soauth.core.uuid import UUID, uuid7

if TYPE_CHECKING:
    from .user import User


class GroupMembership(SQLModel, table=True):
    """
    A record of a user's group membership.
    """

    user_id: Optional[UUID] = Field(
        primary_key=True, foreign_key="user.user_id", ondelete="CASCADE"
    )
    group_id: Optional[UUID] = Field(
        primary_key=True, foreign_key="group.group_id", ondelete="CASCADE"
    )


class Group(SQLModel, table=True):
    group_id: UUID = Field(primary_key=True, default_factory=uuid7)

    group_name: str = Field(unique=True)
    created_by_user_id: UUID = Field(foreign_key="user.user_id")
    created_by: "User" = Relationship(sa_relationship_kwargs=dict(lazy="joined"))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))

    members: list["User"] = Relationship(
        back_populates="groups",
        link_model=GroupMembership,
        sa_relationship_kwargs=dict(lazy="joined"),
    )
    grants: str = Field(default="")

    def has_grant(self, grant: str) -> bool:
        """
        Check if this group posseses the grant `grant`.
        """
        grant = grant.strip().lower().replace(" ", "_")

        if self.grants is None:
            return False
        return grant in self.grants.split(" ")

    def add_grant(self, grant: str):
        """
        Add a grant to the list this group possesses.
        """
        grant = grant.strip().lower().replace(" ", "_")

        if self.has_grant(grant):
            return

        if self.grants is None:
            self.grants = f"{grant}"
            return

        self.grants += f" {grant}"

    def remove_grant(self, grant: str):
        """
        Remove a grant from the list this user possesses.
        """
        grant = grant.strip().lower().replace(" ", "_")
        if not self.has_grant(grant):
            return

        self.grants = " ".join([x for x in self.grants.split(" ") if x != grant])

    def to_core(self) -> GroupData:
        """
        Convert this Group ORM object to a GroupData core object.
        """
        return GroupData(
            group_id=self.group_id,
            group_name=self.group_name,
            created_by=self.created_by.to_core(include_groups=False),
            created_at=self.created_at,
            grants={x for x in self.grants.split(" ") if x},
            members=[member.to_core(include_groups=False) for member in self.members],
        )
