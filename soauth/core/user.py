"""
A shared user object that is serialized.
"""

from pydantic import BaseModel

from soauth.core.members import (
    InstitutionalAffiliationData,
    InstitutionalMembershipData,
    MembershipDetailsData,
)
from soauth.core.uuid import UUID


class UserData(BaseModel):
    user_id: UUID
    user_name: str
    full_name: str | None
    profile_image: str | None
    email: str | None
    grants: set[str] | None
    group_names: list[str] | None
    # UUIDs are not JSON serializable, so we use strings
    group_ids: list[str] | None
    membership: MembershipDetailsData | None = None
    institutions: list[InstitutionalMembershipData] | None = None
    affiliations: list[InstitutionalAffiliationData] | None = None
