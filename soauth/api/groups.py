"""
Group management.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from soauth.api.dependencies import DatabaseDependency, LoggerDependency
from soauth.core.group import GroupData
from soauth.service import groups as groups_service
from soauth.toolkit.fastapi import AuthenticatedUserDependency

group_app = APIRouter(tags=["Group Management"])


@group_app.get(
    "/list",
    summary="List all groups",
    description=(
        "Retrieve a list of all groups. "
        "If users are admins, they are returned a list of all groups, otherwise"
        " they only see groups they are members of."
    ),
    responses={
        200: {"description": "List of groups."},
    },
)
async def list_groups(
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> list[GroupData]:
    """
    List all groups.
    """
    log = log.bind(user_id=user.user_id)

    if "admin" in user.grants:
        for_user = None
    else:
        for_user = user.user_id

    groups = await groups_service.get_group_list(conn=conn, log=log, for_user=for_user)
    await log.adebug("group.list_all")

    return [g.to_core() for g in groups]


@group_app.get(
    "/{group_id}",
    summary="Get group by ID",
    description=(
        "Retrieve a group by its ID, with information about its members. "
        "Users can either be a member of the group or an admin."
    ),
    responses={
        200: {"description": "Group details with members."},
        404: {"description": "Group not found."},
    },
)
async def get_group_by_id(
    group_id: UUID,
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> GroupData:
    """
    Get a group by its ID.
    """
    log = log.bind(group_id=group_id, user_id=user.user_id)
    group = await groups_service.read_by_id(group_id=group_id, conn=conn, log=log)
    await log.adebug("group.found")

    # Access controls: user must either have the admin role, be a member of the group,
    # or be the creator of the group.
    allowed_user_ids = {
        group.created_by.user_id,
        *[member.user_id for member in group.members],
    }

    if "admin" in user.grants:
        allowed_user_ids.add(user.user_id)

    if user.user_id not in allowed_user_ids:
        await log.awarn("group.access_denied")
        raise HTTPException(status_code=404, detail="Access denied to this group")

    return group.to_core()


class GroupCreationRequest(BaseModel):
    """
    Request model for creating a new group.
    """

    group_name: str
    member_ids: list[UUID] = []
    grants: str = ""


@group_app.put(
    "",
    summary="Create a new group",
    description=(
        "Create a new group with the specified name and members. "
        "The creator of the group is automatically added as a member. "
        "Requires admin privileges."
    ),
    responses={
        201: {"description": "Group created successfully."},
        400: {"description": "Invalid input data."},
        403: {"description": "Access denied to create groups."},
    },
)
async def create_group(
    content: GroupCreationRequest,
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> GroupData:
    """
    Create a new group.
    """
    group_name = content.group_name.strip().lower().replace(" ", "_")
    member_ids = content.member_ids
    grants = content.grants.strip()

    log = log.bind(
        group_name=group_name,
        user_id=user.user_id,
        number_of_members=len(member_ids),
        grants=grants,
    )

    if "admin" not in user.grants:
        await log.awarn("group.create.access_denied")
        raise HTTPException(status_code=403, detail="Access denied to create groups")

    group = await groups_service.create(
        group_name=group_name,
        created_by_user_id=user.user_id,
        member_ids=set(member_ids).union(
            {user.user_id}
        ),  # Ensure creator is always a member
        grants=grants,
        conn=conn,
        log=log,
    )

    await log.ainfo("group.created", group_id=group.group_id)

    return group.to_core()


@group_app.delete(
    "/{group_id}",
    summary="Delete a group",
    description=(
        "Delete a group by its ID. "
        "Only the creator of the group or an admin can delete it."
    ),
    responses={
        204: {"description": "Group deleted successfully."},
        404: {"description": "Group not found."},
        403: {"description": "Access denied to delete this group."},
    },
)
async def delete_group(
    group_id: UUID,
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
) -> None:
    """
    Delete a group by its ID.
    """
    log = log.bind(group_id=group_id, user_id=user.user_id)

    group = await groups_service.read_by_id(group_id=group_id, conn=conn, log=log)

    if group.created_by.user_id != user.user_id and "admin" not in user.grants:
        await log.awarn("group.delete.access_denied")
        raise HTTPException(
            status_code=403, detail="Access denied to delete this group"
        )

    await groups_service.delete_group(group_id=group.group_id, conn=conn, log=log)
    await log.ainfo("group.deleted")

    return None


class ChangeGroupMembersRequest(BaseModel):
    """
    Request model for adding or removing members from a group.
    """

    add_user_id: UUID | None = None
    remove_user_id: UUID | None = None


@group_app.post(
    "/{group_id}/members",
    summary="Add or remove a member to a group",
    description=(
        "Add or remove user from a group by their ID. "
        "Only the creator of the group or an admin can add members."
    ),
    responses={
        200: {"description": "Member added successfully."},
        404: {"description": "Group or user not found."},
        403: {"description": "Access denied to add members to this group."},
    },
)
async def change_group_members(
    group_id: UUID,
    user: AuthenticatedUserDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
    content: ChangeGroupMembersRequest,
) -> GroupData:
    """
    Add or remove a user from a group.
    """
    add_user_id = content.add_user_id
    remove_user_id = content.remove_user_id

    log = log.bind(
        group_id=group_id,
        user_id=user.user_id,
        add_user_id=add_user_id,
        remove_user_id=remove_user_id,
    )

    group = await groups_service.read_by_id(group_id=group_id, conn=conn, log=log)

    if group.created_by.user_id != user.user_id and "admin" not in user.grants:
        await log.awarn("group.members.change.access_denied")
        raise HTTPException(
            status_code=403, detail="Access denied to change group members"
        )

    if add_user_id is not None:
        group = await groups_service.add_member(
            group_id=group.group_id,
            user_id=add_user_id,
            conn=conn,
            log=log,
        )
        await log.ainfo("group.member_added", user_id=add_user_id)
    elif remove_user_id is not None:
        group = await groups_service.remove_member(
            group_id=group.group_id,
            user_id=remove_user_id,
            conn=conn,
            log=log,
        )
        await log.ainfo("group.member_removed", user_id=remove_user_id)
    else:
        await log.awarn("group.members.change.no_action")
        raise HTTPException(
            status_code=400, detail="No action specified for member change"
        )

    return group.to_core()
