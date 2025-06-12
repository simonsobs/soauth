"""
Core 'frontend' app, where users can log in and view/update status.
This does not require any access to the database, and purely uses the
soauth authentication scheme. It is packed purely for simplicity.
"""

from json.decoder import JSONDecodeError

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse

from soauth.app.templating import template_endpoint
from soauth.config.settings import Settings
from soauth.toolkit.fastapi import global_setup

from .apps import router as app_router
from .groups import router as group_router
from .keys import router as key_router
from .users import router as user_router

settings = Settings()

if (not settings.create_files) and settings.create_example_app_and_user:
    # Running in example mode; grab data
    with httpx.Client() as client:
        response = client.get(f"{settings.hostname}/developer_details")

        try:
            content = response.json()

            app_id = content["authentication_app_id"]
            public_key = content["authentication_public_key"]
            key_type = content["authentication_key_type"]
            client_secret = content["authentication_client_secret"]
        except (KeyError, JSONDecodeError):
            print(response.content)
            exit(1)
else:
    # Read from files.
    with open(settings.app_id_filename, "r") as handle:
        app_id = handle.read()

    with open(settings.public_key_filename, "r") as handle:
        public_key = handle.read()

    with open(settings.client_secret_filename, "r") as handle:
        client_secret = handle.read()

    key_type = settings.key_pair_type

favicon = FileResponse(
    __file__.replace("app.py", "favicon.ico"), media_type="image/x-icon"
)
apple_touch = FileResponse(
    __file__.replace("app.py", "apple-touch-icon.png"), media_type="image/png"
)


async def lifespan(app: FastAPI):
    app.app_id = str(app_id)
    app.user_list_url = f"{settings.hostname}/admin/users"
    app.user_detail_url = f"{settings.hostname}/admin/user"
    app.key_revoke_url = f"{settings.hostname}/admin/keys"
    app.app_list_url = f"{settings.hostname}/apps/apps"
    app.app_detail_url = f"{settings.hostname}/apps/app"
    app.key_list_url = f"{settings.hostname}/keys/list"
    app.key_detail_url = f"{settings.hostname}/keys/app"
    app.group_detail_url = f"{settings.hostname}/groups"
    app.group_list_url = f"{settings.hostname}/groups/list"
    app.group_grant_update_url = f"{settings.hostname}/admin/group"
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


template_endpoint(app=app, path="/", template="index.html", log_name="app.home")

app.include_router(app_router)
app.include_router(user_router)
app.include_router(key_router)
app.include_router(group_router)
