"""
Membership management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from soauth.api.dependencies import DatabaseDependency, LoggerDependency
from soauth.core.members import InstitutionalMembershipData, InstitutionData
from soauth.core.uuid import UUID
from soauth.service import membership as membership_service
from soauth.service import user as user_service
from soauth.toolkit.fastapi import AuthenticatedUserDependency

membership_app = APIRouter(tags=["Membership Management"])


@membership_app.put(
    "",
    summary="Create a new institution",
    description="Create a new institution, only available to either admins or users "
    "with the membership grant.",
    responses={
        200: {"description": "Institution created."},
        401: {"description": "Unauthorized."},
    },
)
async def create_institution(
    institution: InstitutionData,
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> InstitutionData:
    """
    Create a new institution.
    """
    log = log.bind(user_id=user.user_id)

    if "admin" not in user.grants and "membership" not in user.grants:
        await log.awarning("institution.create_unauthorized")
        raise HTTPException(status_code=401, detail="Unauthorized")

    created_institution = await membership_service.create_institution(
        institution_name=institution.institution_name,
        unit_name=institution.unit_name,
        publication_text=institution.publication_text,
        role=institution.role,
        conn=conn,
        log=log,
    )
    await log.ainfo(
        "institution.created", institution_id=created_institution.institution_id
    )

    return created_institution.to_core()


@membership_app.get(
    "/list",
    summary="List all institutions",
    description="Retrieve a list of all institutions, only available to either admins "
    "or users with the membership grant.",
    responses={
        200: {"description": "List of institutions."},
        401: {"description": "Unauthorized."},
    },
)
async def list_institutions(
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> list[InstitutionData]:
    """
    List all institutions.
    """
    log = log.bind(user_id=user.user_id)

    if "admin" not in user.grants and "membership" not in user.grants:
        await log.awarning("institution.list_unauthorized")
        raise HTTPException(status_code=401, detail="Unauthorized")

    institutions = await membership_service.get_institution_list(conn=conn, log=log)
    await log.adebug("institution.listed")

    return [i.to_core() for i in institutions]


@membership_app.get(
    "/{institution_id}",
    summary="Get institution by ID",
    description="Retrieve an institution by its ID, only available to either admins "
    "or users with the membership grant.",
    responses={
        200: {"description": "Institution details."},
        401: {"description": "Unauthorized."},
        404: {"description": "Institution not found."},
    },
)
async def get_institution(
    institution_id: UUID,
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> dict[str, InstitutionData | list[InstitutionalMembershipData]]:
    """
    Get institution by ID.
    """
    log = log.bind(user_id=user.user_id)

    if "admin" not in user.grants and "membership" not in user.grants:
        await log.awarning(
            "institution.get_unauthorized", institution_id=institution_id
        )
        raise HTTPException(status_code=401, detail="Unauthorized")

    institution = await membership_service.read_by_id(
        institution_id=institution_id, conn=conn, log=log
    )
    await log.adebug("institution.retrieved", institution_id=institution_id)

    members = await membership_service.get_membership_list_of_institution(
        institution_id=institution_id, conn=conn, log=log
    )
    await log.adebug(
        "institution.members_retrieved",
        institution_id=institution_id,
        number_of_members=len(members),
    )

    return {
        "institution": institution.to_core(),
        "members": [x.to_core() for x in members],
    }


@membership_app.post(
    "/{institution_id}/add_member/{user_id}",
    summary="Add a member to an institution",
    description="Add a user as a member to an institution, only available to either "
    "admins or users with the membership grant.",
    responses={
        200: {"description": "User added as member."},
        401: {"description": "Unauthorized."},
        404: {"description": "Institution or user not found."},
        400: {"description": "User is not a member."},
    },
)
async def add_member_to_institution(
    institution_id: UUID,
    user_id: UUID,
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> None:
    """
    Add a member to an institution.
    """
    log = log.bind(
        user_id=user.user_id, institution_id=institution_id, new_member_id=user_id
    )

    if "admin" not in user.grants and "membership" not in user.grants:
        await log.awarning(
            "institution.add_member_unauthorized", institution_id=institution_id
        )
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        await membership_service.add_member_to_institution(
            institution_id=institution_id, user_id=user_id, conn=conn, log=log
        )
        await log.ainfo("institution.member_added")
    except membership_service.UserIsNotMember:
        await log.awarning("add_member.user_not_member")
        raise HTTPException(status_code=400, detail="User is not a member")
    except ValueError:
        await log.awarning("add_member.user_already_member")
        raise HTTPException(
            status_code=400, detail="User is already a member of an institution"
        )

    return None


@membership_app.post(
    "/{institution_id}/swap_member/{user_id}",
    summary="Swap a member's membership institution",
    description="Swap a member's membership institution to another institution, only available to either "
    "admins or users with the membership grant.",
    responses={
        200: {"description": "User's primary institution swapped."},
        401: {"description": "Unauthorized."},
        404: {"description": "Institution or user not found."},
    },
)
async def swap_member_primary_institution(
    institution_id: UUID,
    user_id: UUID,
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> None:
    """
    Swap a member's primary institution.
    """
    log = log.bind(
        user_id=user.user_id, institution_id=institution_id, swapped_member_id=user_id
    )

    if "admin" not in user.grants and "membership" not in user.grants:
        await log.awarning(
            "institution.swap_member_unauthorized", institution_id=institution_id
        )
        raise HTTPException(status_code=401, detail="Unauthorized")

    await membership_service.swap_institution_member_status(
        new_institution_id=institution_id, user_id=user_id, conn=conn, log=log
    )
    await log.ainfo("institution.member_swapped")

    return None


@membership_app.post(
    "/{institution_id}/remove_member/{user_id}",
)
async def remove_member_from_institution():
    raise NotImplementedError()


@membership_app.get(
    "/details/{user_id}",
    summary="Get member details",
    description="Retrieve member details by user ID, only available to either admins "
    "or users with the membership grant.",
    responses={
        200: {"description": "Member details."},
        401: {"description": "Unauthorized."},
        404: {"description": "User not found."},
    },
)
async def get_member_details(
    user_id: UUID,
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> dict:
    """
    Get member details by user ID.
    """
    log = log.bind(user_id=user.user_id, queried_user_id=user_id)

    if "admin" not in user.grants and "membership" not in user.grants:
        await log.awarning(
            "membership.get_details_unauthorized", queried_user_id=user_id
        )
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = await user_service.read_by_id(user_id=user_id, conn=conn)

    await log.adebug("membership.details_retrieved", queried_user_id=user_id)

    if user.membership is None:
        raise HTTPException(status_code=404, detail="User not found")

    return user.membership.to_core()


class PromoteToMemberRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    status: str
    confluence: str | None = None
    website: str | None = None
    orcid: str | None = None


@membership_app.post(
    "/promote/{user_id}",
    summary="Promote a user to member",
    description="Promote a user to member, only available to either admins "
    "or users with the membership grant.",
    responses={
        200: {"description": "User promoted to member."},
        401: {"description": "Unauthorized."},
        404: {"description": "User not found."},
    },
)
async def promote_user_to_member(
    user_id: UUID,
    details: PromoteToMemberRequest,
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> None:
    """
    Promote a user to member.
    """
    log = log.bind(user_id=user.user_id, promoted_user_id=user_id)

    if "admin" not in user.grants and "membership" not in user.grants:
        await log.awarning("membership.promote_unauthorized", promoted_user_id=user_id)
        raise HTTPException(status_code=401, detail="Unauthorized")

    await membership_service.update_user_to_be_member(
        user_id=user_id,
        first_name=details.first_name,
        last_name=details.last_name,
        email=details.email,
        status=details.status,
        confluence=details.confluence,
        website=details.website,
        orcid=details.orcid,
        conn=conn,
        log=log,
    )
    await log.ainfo("membership.user_promoted")

    return None


@membership_app.post(
    "/{institution_id}/affiliate_member/{user_id}",
    summary="Add an affiliated person to an institution",
    description="Add a user as affiliated wtih an institution, only available to either "
    "admins or users with the membership grant.",
    responses={
        200: {"description": "User added as member."},
        401: {"description": "Unauthorized."},
        404: {"description": "Institution or user not found."},
        400: {"description": "User is not a member."},
    },
)
async def affiliate_member_to_institution(
    institution_id: UUID,
    user_id: UUID,
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> None:
    """
    Affiliate a member to an institution; different from setting their primary membership institution.
    """
    log = log.bind(
        user_id=user.user_id, institution_id=institution_id, new_member_id=user_id
    )

    if "admin" not in user.grants and "membership" not in user.grants:
        await log.awarning(
            "institution.affiliate_member_unauthorized", institution_id=institution_id
        )
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        await membership_service.affiliate_member_with_institution(
            institution_id=institution_id, user_id=user_id, conn=conn, log=log
        )
    except ValueError:
        raise HTTPException(
            status_code=400, detail="User is already affiliated with this institution"
        )

    await log.ainfo("institution.member_affiliated")

    return None


@membership_app.post(
    "/{institution_id}/unaffiliate_member/{user_id}",
    summary="Remove an affiliated person from an institution",
    description="Remove a user's affiliation with an institution, only available to either "
    "admins or users with the membership grant.",
    responses={
        200: {"description": "User removed as affiliated person."},
        401: {"description": "Unauthorized."},
        404: {"description": "Institution or user not found."},
        400: {"description": "User is not affiliated."},
    },
)
async def unaffiliate_member_from_institution(
    user_id: UUID,
    institution_id: UUID,
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> None:
    """
    Unaffiliate a member from an institution.
    """
    log = log.bind(
        user_id=user.user_id, institution_id=institution_id, removed_member_id=user_id
    )

    if "admin" not in user.grants and "membership" not in user.grants:
        await log.awarning(
            "institution.unaffiliate_member_unauthorized", institution_id=institution_id
        )
        raise HTTPException(status_code=401, detail="Unauthorized")

    await membership_service.unaffiliate_member_from_institution(
        institution_id=institution_id, user_id=user_id, conn=conn, log=log
    )
    await log.ainfo("institution.member_unaffiliated")

    return None


class ReorderAffiliationsRequest(BaseModel):
    ordered_institution_ids: list[UUID]


@membership_app.post(
    "/reorder_affiliations/{user_id}",
    summary="Reorder a user's institutional affiliations",
    description="Reorder a user's institutional affiliations, only available to either "
    "admins or users with the membership grant.",
    responses={
        200: {"description": "Affiliations reordered."},
        401: {"description": "Unauthorized."},
        404: {"description": "User not found."},
    },
)
async def reorder_affiliations(
    user_id: UUID,
    data: ReorderAffiliationsRequest,
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> None:
    """
    Reorder a user's institutional affiliations.
    """
    log = log.bind(user_id=user.user_id, reordered_user_id=user_id)

    if "admin" not in user.grants and "membership" not in user.grants:
        await log.awarning(
            "membership.reorder_affiliations_unauthorized", reordered_user_id=user_id
        )
        raise HTTPException(status_code=401, detail="Unauthorized")

    await membership_service.reorder_member_affiliations(
        user_id=user_id,
        new_ordering=data.ordered_institution_ids,
        conn=conn,
        log=log,
    )

    await log.ainfo("membership.affiliations_reordered")

    return None
