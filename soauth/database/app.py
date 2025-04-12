"""
Applications/TLDs accessible from the auth server.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

from soauth.core.app import AppData
from soauth.core.uuid import UUID, uuid7

if TYPE_CHECKING:
    from .user import User


class App(SQLModel, table=True):
    app_id: UUID = Field(primary_key=True, default_factory=uuid7)

    created_by_user_id: UUID | None = Field(foreign_key="user.user_id")
    created_by: Optional["User"] = Relationship(
        back_populates="managed_apps", sa_relationship_kwargs=dict(lazy="joined")
    )
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))

    domain: str

    key_pair_type: str
    # Note that the 'public key' is not really public - it should
    # only be shared with the application, as it can be used to decode
    # the signed JWTs.
    public_key: bytes
    private_key: bytes

    def to_core(self) -> AppData:
        return AppData(
            app_id=self.app_id,
            created_by_user_id=self.created_by_user_id,
            created_by_user_name=(
                self.created_by.user_name if self.created_by else "system"
            ),
            created_at=self.created_at,
            domain=self.domain,
        )
