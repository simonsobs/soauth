from typing import Annotated

import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.authentication import requires

from soauth.app.dependencies import LoggerDependency, TemplateDependency
from soauth.app.templating import templateify
from soauth.core.uuid import UUID

router = APIRouter(prefix="/apps")


def check_scope(request):
    if "admin" not in request.auth.scopes:
        if "appmanager" not in request.auth.scopes:
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
@templateify(template_name="apps.html", log_name="app.apps")
def get_app_list(
    request: Request, log: LoggerDependency, templates: TemplateDependency
):
    response = handle_request(url=request.app.app_list_url, request=request)
    return {"apps": response.json()}


@router.get("/create")
@templateify(template_name="app_creation.html", log_name="app.app_creation")
def app_create_form(
    request: Request, log: LoggerDependency, templates: TemplateDependency
):
    check_scope(request=request)
    return


@router.post("/create")
@templateify(template_name="app_detail.html", log_name="app.app_create_post")
def app_create_post(
    request: Request,
    templates: TemplateDependency,
    log: LoggerDependency,
    name: Annotated[str, Form()],
    domain: Annotated[str, Form()],
    redirect: Annotated[str, Form()],
    visibility_grant: Annotated[str | None, Form()] = None,
    api: Annotated[bool | None, Form()] = None,
):
    if api is None:
        api = False

    if not visibility_grant:
        visibility_grant = None

    content = {
        "name": name,
        "domain": domain,
        "redirect_url": redirect,
        "visibility_grant": visibility_grant,
        "api_access": api,
    }

    log = log.bind(**content)

    response = handle_request(
        url=f"{request.app.app_detail_url}",
        request=request,
        method="put",
        json=content,
    )

    log.bind(response=response.json())

    return response.json()


@router.get("/{app_id}")
@templateify(template_name="app_detail.html", log_name="app.app_detail")
def app_detail(
    app_id: UUID,
    request: Request,
    templates: TemplateDependency,
    log: LoggerDependency,
):
    return handle_request(
        url=f"{request.app.app_detail_url}/{app_id}",
        request=request,
    ).json()


@router.get("/{app_id}/revoke/{refresh_key_id}")
@requires("admin")
def revoke_key(
    app_id: UUID,
    refresh_key_id: UUID,
    request: Request,
    log: LoggerDependency,
) -> RedirectResponse:
    log = log.bind(revoke_key=refresh_key_id, user=request.user)
    log.info("app.revoking_key")

    handle_request(
        url=f"{request.app.key_revoke_url}/{refresh_key_id}",
        request=request,
        method="delete",
    )

    return RedirectResponse(
        url=f"{request.app.base_url}/apps/{app_id}", status_code=302
    )


@router.get("/{app_id}/refresh")
@templateify(template_name="app_detail.html", log_name="app.refresh_keys")
def refresh_app_keys(
    app_id: UUID,
    request: Request,
    templates: TemplateDependency,
    log: LoggerDependency,
):
    return handle_request(
        url=f"{request.app.app_detail_url}/{app_id}/refresh",
        request=request,
        method="post",
    ).json()


@router.get("/{app_id}/delete")
def delete_app(
    app_id: UUID,
    request: Request,
    log: LoggerDependency,
):
    handle_request(
        url=f"{request.app.app_detail_url}/{app_id}", method="delete", request=request
    )

    return RedirectResponse(url=f"{request.app.base_url}/apps", status_code=302)
