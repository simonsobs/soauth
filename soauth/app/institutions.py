from typing import Annotated

import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.authentication import requires

from soauth.app.dependencies import LoggerDependency, TemplateDependency
from soauth.app.templating import templateify
from soauth.core.uuid import UUID

router = APIRouter(prefix="/institutions")


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
@templateify(template_name="institutions.html", log_name="app.admin.institutions")
def institutions(request: Request, log: LoggerDependency, templates: TemplateDependency):
    response = handle_request(url=request.app.institution_list_url, request=request)
    return {"institutions": response.json()}


@router.post("/create")
@requires("admin")
def create_institution(
    institution_name: Annotated[str, Form()],
    unit_name: Annotated[str, Form()],
    publication_text: Annotated[str, Form()],
    role: Annotated[str, Form()],
    request: Request,
    log: LoggerDependency,
):
    log = log.bind(user_id=request.user.user_id, institution_name=institution_name, unit_name=unit_name, role=role)
    log.debug("app.admin.institution_create")

    response = handle_request(
        url=request.app.institution_detail_url,
        request=request,
        method="PUT",
        json={
            "institution_name": institution_name,
            "unit_name": unit_name,
            "publication_text": publication_text,
            "role": role,
        },
    )

    return RedirectResponse(
        url=f"{request.app.base_url}/institutions",
        status_code=303,
    )


@router.get("/{institution_id}")
@templateify(template_name="institution_detail.html", log_name="app.admin.institution")
def institution_detail(
    institution_id: UUID,
    request: Request,
    log: LoggerDependency,
    templates: TemplateDependency,
):
    log = log.bind(user_id=request.user.user_id, institution_id=institution_id)
    log.debug("app.admin.institution_detail")

    response = handle_request(
        url=f"{request.app.institution_detail_url}/{institution_id}",
        request=request,
    )

    return response.json()


@router.post("/{institution_id}/add")
def add_member(
    institution_id: UUID,
    user_id: Annotated[str, Form()],
    request: Request,
    log: LoggerDependency,
):
    log = log.bind(user_id=request.user.user_id, institution_id=institution_id, add_user_id=user_id)
    log.debug("app.admin.institution_add_member")

    response = handle_request(
        url=f"{request.app.institution_detail_url}/{institution_id}/add_member/{user_id}",
        request=request,
        method="POST",
    )

    return RedirectResponse(
        url=f"{request.app.base_url}/institutions/{institution_id}",
        status_code=303,
    )