"""
ORM for user information.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

from soauth.core.user import UserData
from soauth.core.uuid import UUID, uuid7
from soauth.database.group import GroupMembership

if TYPE_CHECKING:
    from .app import App
    from .group import Group


class User(SQLModel, table=True):
    user_id: UUID = Field(primary_key=True, default_factory=uuid7)

    full_name: str | None = None
    user_name: str = Field(unique=True)
    email: str | None = None

    # A list of grants (space separated!) that this user has.
    grants: str = Field()

    gh_access_token: str | None = None
    # gh_refresh_token: str | None = None
    gh_profile_image_url: str | None = None
    gh_last_logged_in: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )

    # Access token usage
    last_access_token: UUID | None = None
    last_access_time: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )
    number_of_access_tokens: int = 0

    # Group membership is important! We should always emit it.
    groups: list["Group"] = Relationship(
        back_populates="members",
        link_model=GroupMembership,
        sa_relationship_kwargs=dict(lazy="joined"),
    )

    managed_apps: list["App"] = Relationship(back_populates="created_by")

    def has_grant(self, grant: str) -> bool:
        """
        Check if this user posseses the grant `grant`.
        """
        grant = grant.strip().lower().replace(" ", "_")

        if self.grants is None:
            return False
        return grant in self.grants.split(" ")

    def add_grant(self, grant: str):
        """
        Add a grant to the list this user possesses. If they already have it,
        this function does nothing.

        Note that all changes to the local copy of this data (as performed by
        this function) must be committed to the database separately.
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
        Remove a grant from the list this user possesses. If they do not have it,
        this function does nothing.

        Note that all changes to the local copy of this data (as performed by
        this function) must be committed to the database separately.
        """
        grant = grant.strip().lower().replace(" ", "_")

        if not self.has_grant(grant):
            return

        self.grants = " ".join([x for x in self.grants.split(" ") if x != grant])

    def get_effective_grants(self, include_groups: bool = True) -> set[str]:
        """Get all grants from user + all groups they're members of."""
        all_grants = set()

        # Add user's individual grants
        if self.grants:
            all_grants.update({x for x in self.grants.split() if x})

        # Add grants from all groups
        if include_groups:
            for group in self.groups:
                if group.grants:
                    all_grants.update({x for x in group.grants.split() if x})

        return all_grants

    def has_effective_grant(self, grant: str) -> bool:
        """Check if user has grant either individually or through groups."""
        return grant in self.get_effective_grants()

    def to_public_profile_data(self) -> dict[str, str | None]:
        """Convert user data to public profile format."""
        return {
            "username": self.user_name,
            "full_name": self.full_name,
            "profile_image": self.gh_profile_image_url,
        }

    def to_core(self, include_groups=True) -> UserData:
        return UserData(
            user_id=self.user_id,
            user_name=self.user_name,
            full_name=self.full_name,
            email=self.email,
            grants=self.get_effective_grants(include_groups=include_groups),
            group_names=[x.group_name for x in self.groups] if include_groups else None,
            group_ids=[str(x.group_id) for x in self.groups]
            if include_groups
            else None,
            profile_image=self.gh_profile_image_url,
        )
