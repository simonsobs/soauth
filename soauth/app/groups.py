from typing import Annotated

import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.authentication import requires

from soauth.app.dependencies import LoggerDependency, TemplateDependency
from soauth.app.templating import templateify
from soauth.core.uuid import UUID

router = APIRouter(prefix="/groups")


def check_scope(request):
    if "admin" not in request.auth.scopes:
        raise HTTPException(status_code=401)


def handle_request(url: str, request: Request, method: str = "get", **kwargs):
    response = httpx.request(method=method, url=url, cookies=request.cookies, **kwargs)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    return response


@router.get("")
@templateify(template_name="groups.html", log_name="app.admin.groups")
def groups(request: Request, log: LoggerDependency, templates: TemplateDependency):
    response = handle_request(url=request.app.group_list_url, request=request)
    return {"groups": response.json()}


@router.post("/create")
@requires("admin")
def create_group(
    group_name: Annotated[str, Form()],
    grants: Annotated[str, Form()],
    request: Request,
    log: LoggerDependency,
):
    log = log.bind(user_id=request.user.user_id, group_name=group_name, grants=grants)
    log.debug("app.admin.group_create")

    response = handle_request(
        url=request.app.group_detail_url,
        request=request,
        method="PUT",
        json={
            "group_name": group_name,
            "member_ids": [str(request.user.user_id)],
            "grants": grants,
        },
    )

    return RedirectResponse(
        url=f"{request.app.base_url}/groups/{response.json()['group_id']}",
        status_code=303,
    )


@router.post("/{group_id}/add")
@requires("admin")
def add_user(
    user_id: Annotated[UUID, Form()],
    group_id: UUID,
    request: Request,
    log: LoggerDependency,
):
    log = log.bind(user_id=user_id, group_id=group_id)
    log.debug("app.admin.group_add_user")

    handle_request(
        url=f"{request.app.group_detail_url}/{group_id}/members",
        request=request,
        method="post",
        json={"add_user_id": str(user_id)},
    )

    return RedirectResponse(url=request.headers["Referer"], status_code=303)


@router.get("/{group_id}/remove/{user_id}")
@requires("admin")
def remove_user(
    user_id: UUID,
    group_id: UUID,
    request: Request,
    log: LoggerDependency,
):
    log = log.bind(user_id=user_id, group_id=group_id)
    log.debug("app.admin.group_remove_user")

    handle_request(
        url=f"{request.app.group_detail_url}/{group_id}/members",
        request=request,
        method="post",
        json={"remove_user_id": str(user_id)},
    )

    return RedirectResponse(url=request.headers["Referer"], status_code=303)


@router.get("/{group_id}")
@templateify(template_name="group_detail.html", log_name="app.group.group_detail")
def group_detail(
    group_id: UUID,
    request: Request,
    log: LoggerDependency,
    templates: TemplateDependency,
):
    response = handle_request(
        url=f"{request.app.group_detail_url}/{group_id}", request=request
    )
    return {"group": response.json()}


@router.get("/{group_id}/delete")
@requires("admin")
def delete_group(
    group_id: UUID,
    request: Request,
    log: LoggerDependency,
):
    log = log.bind(group_id=group_id)
    log.debug("app.admin.group_delete")

    handle_request(
        url=f"{request.app.group_detail_url}/{group_id}",
        request=request,
        method="delete",
    )

    return RedirectResponse(url=f"{request.app.base_url}/groups", status_code=303)


@router.post("/{group_id}/grant_add")
@requires("admin")
def add_grant(
    grant: Annotated[str, Form()],
    group_id: UUID,
    request: Request,
    log: LoggerDependency,
):
    log = log.bind(group_id=group_id, grant_add_field=grant)
    log.debug("app.admin.group_grant_add")

    if " " in grant or grant == "":
        return RedirectResponse(
            url=f"{request.app.base_url}/groups/{group_id}", status_code=303
        )

    handle_request(
        url=f"{request.app.group_grant_update_url}/{group_id}",
        request=request,
        method="post",
        json={"grant_add": grant},
    )

    return RedirectResponse(
        url=f"{request.app.base_url}/groups/{group_id}", status_code=303
    )


@router.post("/{group_id}/grant_remove")
@requires("admin")
def remove_grant(
    grant: Annotated[str, Form()],
    group_id: UUID,
    request: Request,
    log: LoggerDependency,
):
    log = log.bind(group_id=group_id, grant_remove_field=grant)
    log.debug("app.admin.group_grant_remove")

    if " " in grant or grant == "":
        return RedirectResponse(
            url=f"{request.app.base_url}/groups/{group_id}", status_code=303
        )

    handle_request(
        url=f"{request.app.group_grant_update_url}/{group_id}",
        request=request,
        method="post",
        json={"grant_remove": grant},
    )

    return RedirectResponse(
        url=f"{request.app.base_url}/groups/{group_id}", status_code=303
    )
