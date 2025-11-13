"""
Membership information.
"""

from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel
from soauth.core.uuid import UUID, uuid7
from typing import TYPE_CHECKING, Optional
from soauth.core.members import MembershipDetailsData


from soauth.core.members import InstitutionData, InstitutionalMembershipData, InstitutionalAffiliationData

if TYPE_CHECKING:
    from .user import User


class UserIsNotMember(Exception):
    pass


class InstitutionNotFound(Exception):
    pass


class Institution(SQLModel, table=True):
    __tablename__ = "institution"
    
    institution_id: UUID = Field(primary_key=True, default_factory=uuid7)

    institution_name: str
    unit_name: str

    publication_text: str

    role: str | None = None

    members: list["UserInstitutionalMembership"] = Relationship(
        back_populates="institution"
    )

    affiliates: list["UserInstitutionalAffiliation"] = Relationship(
        back_populates="institution"
    )

    def to_core(self) -> "InstitutionData":
        from soauth.core.members import InstitutionData

        return InstitutionData(
            institution_id=self.institution_id,
            institution_name=self.institution_name,
            unit_name=self.unit_name,
            publication_text=self.publication_text,
            role=self.role,
        )


class UserInstitutionalMembership(SQLModel, table=True):
    __tablename__ = "user_institutional_membership"

    institution_id: Optional[UUID] = Field(
        primary_key=True, foreign_key="institution.institution_id", ondelete="CASCADE"
    )
    user_id: Optional[UUID] = Field(
        primary_key=True, foreign_key="user.user_id", ondelete="CASCADE"
    )

    institution: "Institution" = Relationship(back_populates="members")
    user: "User" = Relationship(back_populates="institutions")

    member_since: datetime = Field(default_factory=datetime.now)
    member_until: datetime | None = None

    current_member: bool = True

    def to_core(self) -> InstitutionalMembershipData:
        return InstitutionalMembershipData(
            user_id=self.user_id,
            institution_id=self.institution_id,
            user_name=self.user.user_name,
            first_name=self.user.membership.first_name,
            last_name=self.user.membership.last_name,
            membership_details=self.user.membership.to_core(), # Do not need to guard against None because must be membership to have an institutional membership
            institutional_member_since=self.member_since,
            institutional_member_until=self.member_until,
            institutional_current_member=self.current_member,
        )
    

class UserInstitutionalAffiliation(SQLModel, table=True):
    __tablename__ = "user_institutional_affiliation"

    affiliation_id: UUID = Field(primary_key=True, default_factory=uuid7)

    institution_id: Optional[UUID] = Field(
        foreign_key="institution.institution_id", ondelete="CASCADE"
    )
    user_id: Optional[UUID] = Field(
        foreign_key="user.user_id", ondelete="CASCADE"
    )

    institution: "Institution" = Relationship(back_populates="affiliates")
    user: "User" = Relationship(back_populates="affiliations")

    affiliated_since: datetime = Field(default_factory=datetime.now)
    affiliated_until: datetime | None = None

    currently_affiliated: bool = True
    ordering: int | None = 0

    def to_core(self) -> InstitutionalAffiliationData:
        return InstitutionalAffiliationData(
            user_id=self.user_id,
            institution_id=self.institution_id,
            user_name=self.user.user_name,
            first_name=self.user.membership.first_name,
            last_name=self.user.membership.last_name,
            institution_name=self.institution.institution_name,
            unit_name=self.institution.unit_name,
            publication_text=self.institution.publication_text,
            affiliated_since=self.affiliated_since,
            currently_affiliated=self.currently_affiliated,
            ordering=self.ordering,
        )
    

class MembershipDetails(SQLModel, table=True):
    __tablename__ = "membership_details"

    membership_details_id: UUID = Field(primary_key=True, default_factory=uuid7)

    user_id: Optional[UUID] = Field(foreign_key="user.user_id")
    # No cascade delete: we want to retain the memebership details even
    # if the user's 'login' details are somehow deleted.
    user: "User" = Relationship(back_populates="membership")

    member_since: datetime = Field(default_factory=datetime.now)
    member_until: datetime | None = None
    current_member: bool = True

    revision: int = Field(default=0)

    first_name: str
    last_name: str

    email: str
    status: str

    github: str | None = None
    confluence: str | None = None
    website: str | None = None
    orcid: str | None = None

    previous: Optional["MembershipDetails"] = Relationship()
    previous_id: UUID | None = Field(
        foreign_key="membership_details.membership_details_id", default=None
    )

    def update(
        self,
        *,
        member_since: datetime | None = None,
        member_until: datetime | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        status: str | None = None,
        github: str | None = None,
        confluence: str | None = None,
        website: str | None = None,
        orcid: str | None = None,
    ) -> "MembershipDetails":
        return MembershipDetails(
            member_since=member_since or self.member_since,
            member_until=member_until or self.member_until,
            current_member=(
                (member_until is None)
                if member_until is not None
                else self.current_member
            ),
            revision=self.revision + 1,
            first_name=first_name or self.first_name,
            last_name=last_name or self.last_name,
            email=email or self.email,
            status=status or self.status,
            github=github or self.github,
            confluence=confluence or self.confluence,
            website=website or self.website,
            orcid=orcid or self.orcid,
            previous=self,
            user=self.user,
        )

    def to_core(self) -> "MembershipDetailsData":
        return MembershipDetailsData(
            membership_details_id=self.membership_details_id,
            status=self.status,
            member_since=self.member_since,
            member_until=self.member_until,
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
            confluence=self.confluence,
            website=self.website,
            orcid=self.orcid,
        )
