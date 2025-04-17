from typing import Annotated

import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.authentication import requires

from soauth.app.dependencies import LoggerDependency, TemplateDependency
from soauth.app.templating import templateify
from soauth.core.uuid import UUID

router = APIRouter(prefix="/users")


def check_scope(request):
    if "admin" not in request.auth.scopes:
        raise HTTPException(status_code=401)


def handle_request(url: str, request: Request, method: str = "get", **kwargs):
    check_scope(request=request)

    response = httpx.request(method=method, url=url, cookies=request.cookies, **kwargs)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    return response


@router.get("/")
@templateify(template_name="users.html", log_name="app.admin.users")
def users(request: Request, log: LoggerDependency, templates: TemplateDependency):
    response = handle_request(url=request.app.user_list_url, request=request)
    return {"users": response.json()}


@router.get("/{user_id}")
@templateify(template_name="user_detail.html", log_name="app.admin.user_detail")
def user_detail(
    user_id: UUID,
    request: Request,
    log: LoggerDependency,
    templates: TemplateDependency,
):
    response = handle_request(
        url=f"{request.app.user_detail_url}/{user_id}", request=request
    )
    other_user = response.json()
    return {
        "other_user": other_user["user"],
        "other_user_logins": other_user["logins"],
    }


@router.get("/{user_id}/delete")
@requires("admin")
def user_delete(user_id: UUID, request: Request, log: LoggerDependency):
    log = log.bind(user_id=user_id)
    log.debug("app.admin.user_delete")

    handle_request(
        url=f"{request.app.user_detail_url}/{user_id}",
        request=request,
        method="delete",
    )

    return RedirectResponse(url=f"{request.app.base_url}/users")


@router.post("/{user_id}/grant_add")
@requires("admin")
def add_grant(
    grant: Annotated[str, Form()],
    user_id: UUID,
    request: Request,
    log: LoggerDependency,
):
    log = log.bind(user_id=user_id, grant_add_field=grant)
    log.debug("app.admin.grant_add_field")

    if " " in grant or grant == "":
        return RedirectResponse(url=f"/users/{user_id}", status_code=303)

    handle_request(
        url=f"{request.app.user_detail_url}/{user_id}",
        request=request,
        method="post",
        json={"grant_add": grant},
    )

    return RedirectResponse(
        url=f"{request.app.base_url}/users/{user_id}", status_code=303
    )


@router.post("/{user_id}/grant_remove")
@requires("admin")
def remove_grant(
    grant: Annotated[str, Form()],
    user_id: UUID,
    request: Request,
    log: LoggerDependency,
):
    log = log.bind(user_id=user_id, grant_remove_field=grant)
    log.debug("app.admin.grant_remove_field")

    if " " in grant or grant == "":
        return RedirectResponse(
            url=f"{request.app.base_url}/users/{user_id}", status_code=303
        )

    handle_request(
        url=f"{request.app.user_detail_url}/{user_id}",
        request=request,
        method="post",
        json={"grant_remove": grant},
    )

    return RedirectResponse(
        url=f"{request.app.base_url}/users/{user_id}", status_code=303
    )
