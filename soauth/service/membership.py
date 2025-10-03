"""
Service layer implementing membership-related logic.
"""

from datetime import datetime
from sqlalchemy import select
from soauth.database.members import Institution, MembershipDetails, UserInstitutionalMembership, UserIsNotMember, InstitutionNotFound
from soauth.database.user import User

from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger
from sqlalchemy.orm import selectinload

from . import user as user_service

from soauth.core.uuid import UUID


async def create_institution(
    institution_name: str,
    unit_name: str,
    publication_text: str,
    role: str | None,
    conn: AsyncSession,
    log: FilteringBoundLogger
) -> Institution:
    """
    Create a new institution entry.

    Parameters
    ----------
    institution_name
        Name of the institution.
    unit_name
        Name of the unit within the institution.
    publication_text
        Text to be used in publications (i.e. the address)
    role
        Role of the instituion within SO.
    """

    log = log.bind(institution_name=institution_name, unit_name=unit_name, role=role)

    institution = Institution(
        institution_name=institution_name,
        unit_name=unit_name,
        publication_text=publication_text,
        role=role
    )

    conn.add(institution)
    await conn.flush()

    await log.ainfo("institution.created", institution_id=str(institution.institution_id))
    return institution


async def get_institution_list(
    conn: AsyncSession,
    log: FilteringBoundLogger
) -> list[Institution]:
    """
    Get a list of all institutions.
    """

    result = await conn.execute(
        select(Institution)
    )

    institutions = result.unique().scalars().all()

    log.info("institution.listed", number_of_institutions=len(institutions))

    return institutions 


async def read_by_id(
    institution_id: UUID,
    conn: AsyncSession,
    log: FilteringBoundLogger
) -> Institution | None:
    """
    Read an institution by its ID.
    """

    log = log.bind(institution_id=institution_id)

    result = await conn.execute(select(Institution).where(Institution.institution_id == institution_id))

    institution = result.scalar_one_or_none()

    if institution is None:
        log.awarning("institution.not_found")
        raise InstitutionNotFound(
            f"Institution {institution_id} not found"
        )

    await log.ainfo("institution.read")

    return institution


async def add_member_to_institution(
    institution_id: UUID,
    user_id: UUID,
    conn: AsyncSession,
    log: FilteringBoundLogger
) -> None:
    """
    Add a user as a member to an institution.
    """

    log = log.bind(institution_id=institution_id, user_id=user_id)

    institution = await read_by_id(institution_id=institution_id, conn=conn, log=log)
    user = await user_service.read_by_id(user_id=user_id, conn=conn)

    if not user.membership:
        await log.ainfo("add_member.user_not_member")
        raise UserIsNotMember(
            f"User {user.user_id} is not a member"
        )

    membership = UserInstitutionalMembership(
        institution=institution,
        user=user,
        current_member=True,
    )

    conn.add(membership)
    await conn.flush()

    log.info("institution.member_added")


async def get_membership_list_of_institution(
    institution_id: UUID,
    conn: AsyncSession,
    log: FilteringBoundLogger
) -> list[UserInstitutionalMembership]:
    """
    Get a list of all members of an institution.
    """

    log = log.bind(institution_id=institution_id)

    result = await conn.execute(
        select(UserInstitutionalMembership).where(
            UserInstitutionalMembership.institution_id == institution_id
        ).options(
            selectinload(UserInstitutionalMembership.user)
        )
    )

    memberships = result.unique().scalars().all()

    log.info("institution.members_listed", number_of_members=len(memberships))

    return memberships
    

async def update_user_to_be_member(
    user_id: UUID,
    first_name: str,
    last_name: str,
    email: str,
    status: str,
    confluence: str | None,
    website: str | None,
    orcid: str | None,
    conn: AsyncSession,
    log: FilteringBoundLogger,

):
    log = log.bind(user_id=user_id, first_name=first_name, last_name=last_name)
    
    user = await user_service.read_by_id(user_id=user_id, conn=conn)

    member_details = MembershipDetails(
        user=user,
        first_name=first_name,
        last_name=last_name,
        email=email,
        status=status,
        confluence=confluence,
        website=website,
        orcid=orcid,
        github=user.user_name,
        previous=None,
    )

    conn.add(member_details)
    await conn.flush()

    await log.ainfo("membership.created")

    return member_details


async def update_membership_details(
    user_id: UUID,
    member_since: datetime | None,
    member_until: datetime | None,
    first_name: str | None,
    last_name: str | None,
    email: str | None,
    status: str | None,
    github: str | None,
    confluence: str | None,
    website: str | None,
    orcid: str | None,
    conn: AsyncSession,
    log: FilteringBoundLogger
):
    log = log.bind(user_id=user_id)

    user = await user_service.read(user_id)

    if not user.membership:
        await log.awarning("update_membership.not_a_member")
        raise UserIsNotMember(
            f"User {user_id} is not a member"
        )
    
    new_membership = user.membership.update(
        member_since=member_since,
        member_until=member_until,
        first_name=first_name,
        last_name=last_name,
        email=email,
        status=status,
        github=github,
        confluence=confluence,
        website=website,
        orcid=orcid,
    )

    user.membership_details_id = new_membership.membership_details_id
    user.membership = new_membership

    conn.add_all([new_membership, user])
    await conn.flush()

    await log.ainfo("membership.updated")

    return new_membership