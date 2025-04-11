"""
Core 'frontend' app, where users can log in and view/update status.
This does not require any access to the database, and purely uses the
soauth authentication scheme. It is packed purely for simplicity.
"""

from typing import Annotated

import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.authentication import requires
from starlette.middleware.authentication import AuthenticationMiddleware

from soauth.core.uuid import UUID
from soauth.toolkit.starlette import SOAuthCookieBackend, on_auth_error

from .dependencies import LoggerDependency

AUTHENTICATION_SERVICE_URL = "http://localhost:8000"

templates = Jinja2Templates(directory=__file__.replace("app.py", "templates"))

# Grab the details
with httpx.Client() as client:
    response = client.get(f"{AUTHENTICATION_SERVICE_URL}/developer_details")

    content = response.json()

    app_id = content["authentication_app_id"]
    public_key = content["authentication_public_key"]
    key_type = content["authentication_key_type"]


async def lifespan(app: FastAPI):
    app.login_url = f"{AUTHENTICATION_SERVICE_URL}/login/{app_id}"
    app.logout_url = f"{AUTHENTICATION_SERVICE_URL}/logout"
    app.refresh_url = f"{AUTHENTICATION_SERVICE_URL}/exchange"
    app.user_list_url = f"{AUTHENTICATION_SERVICE_URL}/admin/users"
    app.user_detail_url = f"{AUTHENTICATION_SERVICE_URL}/admin/user"

    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    AuthenticationMiddleware,
    backend=SOAuthCookieBackend(
        public_key=public_key.encode("utf-8"),
        key_pair_type=key_type,
    ),
    on_error=on_auth_error,
)


@app.get("/")
def home(
    request: Request,
    log: LoggerDependency,
):
    log.debug("app.request.home")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=dict(
            user=request.user,
            scopes=request.auth.scopes,
            login=request.app.login_url,
            logout=request.app.logout_url,
            user_list="users",
        ),
    )


@app.get("/users")
@requires("admin")
def users(request: Request, log: LoggerDependency):
    log.debug("app.admin.users")

    response = httpx.get(url=app.user_list_url, cookies=request.cookies)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    users = response.json()

    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context=dict(
            user=request.user,
            scopes=request.auth.scopes,
            users=users,
        ),
    )


@app.get("/users/{user_id}")
@requires("admin")
def user_detail(user_id: UUID, request: Request, log: LoggerDependency):
    log.debug("app.admin.use_detail")

    response = httpx.get(
        url=f"{app.user_detail_url}/{user_id}", cookies=request.cookies
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    other_user = response.json()

    return templates.TemplateResponse(
        request=request,
        name="user_detail.html",
        context=dict(
            user=request.user, scopes=request.auth.scopes, other_user=other_user
        ),
    )


@app.get("/users/{user_id}/delete")
@requires("admin")
def user_delete(user_id: UUID, request: Request, log: LoggerDependency):
    log = log.bind(user_id=user_id)
    log.debug("app.admin.user_delete")

    response = httpx.delete(
        url=f"{app.user_detail_url}/{user_id}", cookies=request.cookies
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    return RedirectResponse(url="/users")


@app.post("/users/{user_id}/grant_add")
@requires("admin")
def add_grant(
    grant: Annotated[str, Form()],
    user_id: UUID,
    request: Request,
    log: LoggerDependency,
):
    log = log.bind(user_id=user_id, grant_add_field=grant)
    log.debug("app.admin.grant_add_field")

    response = httpx.post(
        url=f"{app.user_detail_url}/{user_id}",
        cookies=request.cookies,
        json={"grant_add": grant},
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    return RedirectResponse(url=f"/users/{user_id}", status_code=303)


@app.post("/users/{user_id}/grant_remove")
@requires("admin")
def remove_grant(
    grant: Annotated[str, Form()],
    user_id: UUID,
    request: Request,
    log: LoggerDependency,
):
    log = log.bind(user_id=user_id, grant_remove_field=grant)
    log.debug("app.admin.grant_remove_field")

    response = httpx.post(
        url=f"{app.user_detail_url}/{user_id}",
        cookies=request.cookies,
        json={"grant_remove": grant},
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    return RedirectResponse(url=f"/users/{user_id}", status_code=303)
