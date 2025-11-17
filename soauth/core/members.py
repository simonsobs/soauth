"""\
Membership models.
"""

from datetime import datetime

from pydantic import BaseModel, model_validator

from soauth.core.uuid import UUID


class InstitutionData(BaseModel):
    institution_id: UUID | None = None
    institution_name: str
    unit_name: str
    publication_text: str
    role: str | None = None


class MembershipDetailsData(BaseModel):
    membership_details_id: UUID
    member_since: datetime | None = None
    member_until: datetime | None = None
    status: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    country: str | None = None
    confluence: str | None = None
    website: str | None = None
    orcid: str | None = None


class InstitutionalMembershipData(BaseModel):
    user_id: UUID
    institution_id: UUID

    user_name: str
    institution_name: str

    first_name: str
    last_name: str

    institutional_member_since: datetime
    institutional_member_until: datetime | None = None

    institutional_current_member: bool


class InstitutionalAffiliationData(BaseModel):
    user_id: UUID
    institution_id: UUID

    user_name: str
    institution_name: str

    first_name: str
    last_name: str

    unit_name: str
    publication_text: str

    affiliated_since: datetime
    affiliated_until: datetime | None = None

    currently_affiliated: bool
    ordering: int | None = None

    @model_validator(mode="after")
    def check_ordering(self):
        if self.currently_affiliated and self.ordering is None:
            raise ValueError(
                "If 'currently_affiliated' is True, 'ordering' must be an integer."
            )
        if not self.currently_affiliated and self.ordering is not None:
            raise ValueError(
                "If 'currently_affiliated' is False, 'ordering' must be None."
            )
        return self
