
import httpx
from fastapi import APIRouter, HTTPException, Request

from soauth.app.dependencies import LoggerDependency, TemplateDependency
from soauth.app.templating import templateify

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
