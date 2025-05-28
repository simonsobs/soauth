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
