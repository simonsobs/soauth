"""
Core 'frontend' app, where users can log in and view/update status.
This does not require any access to the database, and purely uses the
soauth authentication scheme. It is packed purely for simplicity.
"""

from datetime import timedelta
from typing import Annotated

import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.authentication import requires

from soauth.config.settings import Settings
from soauth.core.uuid import UUID
from soauth.toolkit.fastapi import global_setup

from .dependencies import LoggerDependency

settings = Settings()

if (not settings.create_files) and settings.create_example_app_and_user:
    # Running in example mode; grab data
    with httpx.Client() as client:
        response = client.get(f"{settings.hostname}/developer_details")

        content = response.json()

        app_id = content["authentication_app_id"]
        public_key = content["authentication_public_key"]
        key_type = content["authentication_key_type"]
        client_secret = content["authentication_client_secret"]
else:
    # Read from files.
    with open(settings.app_id_filename, "r") as handle:
        app_id = handle.read()

    with open(settings.public_key_filename, "r") as handle:
        public_key = handle.read()

    with open(settings.client_secret_filename, "r") as handle:
        client_secret = handle.read()

    key_type = settings.key_pair_type


templates = Jinja2Templates(directory=__file__.replace("app.py", "templates"))
favicon = FileResponse(
    __file__.replace("app.py", "favicon.ico"), media_type="image/x-icon"
)
apple_touch = FileResponse(
    __file__.replace("app.py", "apple-touch-icon.png"), media_type="image/png"
)


async def lifespan(app: FastAPI):
    app.user_list_url = f"{settings.hostname}/admin/users"
    app.user_detail_url = f"{settings.hostname}/admin/user"
    app.key_revoke_url = f"{settings.hostname}/admin/keys"
    app.app_list_url = f"{settings.hostname}/apps/apps"
    app.app_detail_url = f"{settings.hostname}/apps/app"
    app.cookie_max_age = timedelta(days=7)

    app.user_list = f"{settings.management_hostname}{settings.management_path}/users"
    app.app_list = f"{settings.management_hostname}{settings.management_path}/apps"
    app.logout_url = f"{settings.management_hostname}{settings.management_path}/logout"

    yield


app = FastAPI(lifespan=lifespan, root_path=settings.management_path)

app = global_setup(
    app=app,
    app_base_url=f"{settings.management_hostname}{settings.management_path}",
    authentication_base_url=settings.hostname,
    app_id=app_id,
    client_secret=client_secret,
    public_key=public_key,
    key_pair_type=key_type,
)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_call():
    return favicon


@app.get("/apple-touch-ico{param}.png", include_in_schema=False)
async def apple(param: str | None):
    return apple_touch


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
            user_list=request.app.user_list,
            apps_list=request.app.app_list,
            base_url=request.app.base_url,
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
            login=request.app.login_url,
            logout=request.app.logout_url,
            user_list=request.app.user_list,
            apps_list=request.app.app_list,
            base_url=request.app.base_url,
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
            user=request.user,
            scopes=request.auth.scopes,
            other_user=other_user["user"],
            other_user_logins=other_user["logins"],
            login=request.app.login_url,
            logout=request.app.logout_url,
            user_list=request.app.user_list,
            apps_list=request.app.app_list,
            base_url=request.app.base_url,
        ),
    )


# Not working
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

    return RedirectResponse(url=f"{app.base_url}/users")


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

    if " " in grant or grant == "":
        return RedirectResponse(url=f"/users/{user_id}", status_code=303)

    response = httpx.post(
        url=f"{app.user_detail_url}/{user_id}",
        cookies=request.cookies,
        json={"grant_add": grant},
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    return RedirectResponse(url=f"{app.base_url}/users/{user_id}", status_code=303)


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

    if " " in grant or grant == "":
        return RedirectResponse(url=f"{app.base_url}/users/{user_id}", status_code=303)

    response = httpx.post(
        url=f"{app.user_detail_url}/{user_id}",
        cookies=request.cookies,
        json={"grant_remove": grant},
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    return RedirectResponse(url=f"{app.base_url}/users/{user_id}", status_code=303)


@app.get("/apps")
def list_apps(request: Request, log: LoggerDependency):
    # Manual because we got an either OR situation
    if "admin" not in request.auth.scopes:
        if "appmanager" not in request.auth.scopes:
            raise HTTPException(status_code=401)

    response = httpx.get(url=app.app_list_url, cookies=request.cookies)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    content = response.json()
    return templates.TemplateResponse(
        request=request,
        name="apps.html",
        context=dict(
            user=request.user,
            scopes=request.auth.scopes,
            login=request.app.login_url,
            logout=request.app.logout_url,
            apps=content,
            user_list=request.app.user_list,
            apps_list=request.app.app_list,
            base_url=request.app.base_url,
        ),
    )


@app.get("/apps/create")
def app_create_form(request: Request, log: LoggerDependency):
    # Manual because we got an either OR situation
    if "admin" not in request.auth.scopes:
        if "appmanager" not in request.auth.scopes:
            raise HTTPException(status_code=401)

    return templates.TemplateResponse(
        request=request,
        name="app_creation.html",
        context=dict(
            user=request.user,
            scopes=request.auth.scopes,
            login=request.app.login_url,
            logout=request.app.logout_url,
            user_list=request.app.user_list,
            apps_list=request.app.app_list,
            base_url=request.app.base_url,
        ),
    )


@app.post("/apps/create")
def app_create_post(
    domain: Annotated[str, Form()],
    redirect: Annotated[str, Form()],
    request: Request,
    log: LoggerDependency,
):
    if "admin" not in request.auth.scopes:
        if "appmanager" not in request.auth.scopes:
            raise HTTPException(status_code=401)

    log = log.bind(domain=domain)
    log.info("app.apps.create.submitting")

    response = httpx.put(
        f"{request.app.app_detail_url}",
        cookies=request.cookies,
        params={"domain": domain, "redirect_url": redirect},
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    content = response.json()

    return templates.TemplateResponse(
        request=request,
        name="app_detail.html",
        context=dict(
            user=request.user,
            scopes=request.auth.scopes,
            login=request.app.login_url,
            logout=request.app.logout_url,
            public_key=content["public_key"],
            key_pair_type=content["key_pair_type"],
            app=content["app"],
            client_secret=content["client_secret"],
            user_list=request.app.user_list,
            apps_list=request.app.app_list,
            base_url=request.app.base_url,
        ),
    )


@app.get("/apps/{app_id}")
def app_detail(
    app_id: UUID,
    request: Request,
    log: LoggerDependency,
):
    # Manual because we got an either OR situation
    if "admin" not in request.auth.scopes:
        if "appmanager" not in request.auth.scopes:
            raise HTTPException(status_code=401)

    response = httpx.get(url=f"{app.app_detail_url}/{app_id}", cookies=request.cookies)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    content = response.json()
    return templates.TemplateResponse(
        request=request,
        name="app_detail.html",
        context=dict(
            user=request.user,
            scopes=request.auth.scopes,
            login=request.app.login_url,
            logout=request.app.logout_url,
            app=content["app"],
            logged_in_users=content["users"],
            user_list=request.app.user_list,
            apps_list=request.app.app_list,
            base_url=request.app.base_url,
        ),
    )


@app.get("/apps/{app_id}/revoke/{refresh_key_id}")
@requires("admin")
def revoke_key(
    app_id: UUID,
    refresh_key_id: UUID,
    request: Request,
    log: LoggerDependency,
) -> RedirectResponse:
    response = httpx.delete(
        f"{app.key_revoke_url}/{refresh_key_id}", cookies=request.cookies
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    return RedirectResponse(
        url=f"{request.app.base_url}/apps/{app_id}", status_code=302
    )


@app.get("/apps/{app_id}/refresh")
def refresh_app_keys(
    app_id: UUID,
    request: Request,
    log: LoggerDependency,
):
    # Manual because we got an either OR situation
    if "admin" not in request.auth.scopes:
        if "appmanager" not in request.auth.scopes:
            raise HTTPException(status_code=401)

    response = httpx.post(
        f"{app.app_detail_url}/{app_id}/refresh", cookies=request.cookies
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    content = response.json()
    return templates.TemplateResponse(
        request=request,
        name="app_detail.html",
        context=dict(
            user=request.user,
            scopes=request.auth.scopes,
            login=request.app.login_url,
            logout=request.app.logout_url,
            app=content["app"],
            public_key=content["public_key"],
            key_pair_type=content["key_pair_type"],
            client_secret=content["client_secret"],
            user_list=request.app.user_list,
            apps_list=request.app.app_list,
            base_url=request.app.base_url,
        ),
    )


@app.get("/apps/{app_id}/delete")
def delete_app(
    app_id: UUID,
    request: Request,
    log: LoggerDependency,
):
    # Manual because we got an either OR situation
    if "admin" not in request.auth.scopes:
        if "appmanager" not in request.auth.scopes:
            raise HTTPException(status_code=401)

    response = httpx.delete(f"{app.app_detail_url}/{app_id}", cookies=request.cookies)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Error from downstream API")

    return RedirectResponse(url=f"{app.base_url}/apps", status_code=302)
