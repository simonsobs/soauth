"""
API Key management.
"""

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from soauth.app.dependencies import LoggerDependency, TemplateDependency
from soauth.app.templating import templateify
from soauth.core.uuid import UUID

router = APIRouter(prefix="/keys")


def handle_request(url: str, request: Request, method: str = "get", **kwargs):
    response = httpx.request(method=method, url=url, cookies=request.cookies, **kwargs)  # noqa: F821

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    return response


@router.get("/")
@templateify(template_name="keys.html", log_name="app.keys.list")
def keys(request: Request, log: LoggerDependency, templates: TemplateDependency):
    response = handle_request(url=request.app.key_list_url, request=request)
    return {"apps": response.json()}


@router.get("/{app_id}")
@templateify(template_name="key_detail.html", log_name="app.keys.list")
def create_keys(
    app_id: UUID, request: Request, log: LoggerDependency, templates: TemplateDependency
):
    response = handle_request(
        url=f"{request.app.key_detail_url}/{app_id}", request=request
    )
    return response.json()


@router.get("/revoke/{refresh_key_id}")
def revoke_key(
    refresh_key_id: UUID,
    request: Request,
    log: LoggerDependency,
) -> RedirectResponse:
    log = log.bind(revoke_key=refresh_key_id, user=request.user)
    log.info("app.revoking_key")

    handle_request(
        url=f"{request.app.expire_url}/{refresh_key_id}",
        request=request,
        method="delete",
    )

    return RedirectResponse(url=f"{request.app.base_url}/keys", status_code=302)
