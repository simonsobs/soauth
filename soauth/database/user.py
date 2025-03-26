"""
ORM for user information.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from soauth.core.user import UserData


class User(SQLModel):
    uid: int = Field(primary_key=True)

    username: str = Field(unique=True)
    email: str

    # A list of grants (space separated!) that this user has.
    grants: str = Field()

    gh_access_token: str | None = None
    gh_refresh_token: str | None = None
    gh_last_logged_in: datetime | None = None

    # Need to link to group membership AND MAKE SURE CASCADING DELETE WORKS
    groups = []

    def has_grant(self, grant: str) -> bool:
        """
        Check if this user posseses the grant `grant`.
        """
        return grant in self.grants.split(" ")

    def add_grant(self, grant: str):
        """
        Add a grant to the list this user possesses. If they already have it,
        this function does nothing.

        Note that all changes to the local copy of this data (as performed by
        this function) must be committed to the database separately.
        """
        if self.has_grant(grant):
            return

        self.grants += f" {grant}"

    def remove_grant(self, grant: str):
        """
        Remove a grant from the list this user possesses. If they do not have it,
        this function does nothing.

        Note that all changes to the local copy of this data (as performed by
        this function) must be committed to the database separately.
        """
        if not self.has_grant(grant):
            return

        self.grants = " ".join([x for x in self.grants.split(" ") if x != grant])

    def to_core(self) -> UserData:
        return UserData(
            uid=self.uid,
            username=self.username,
            email=self.email,
            grants=set(self.grants.split(" ")),
            groups=set(x.name for x in self.groups),
        )
