"""
FastAPI app
"""

from fastapi import FastAPI

from soauth.toolkit.fastapi import add_exception_handlers

from .admin import admin_app
from .appmanager import app_manager_app
from .dependencies import SETTINGS
from .login import login_app

settings = SETTINGS()


async def lifespan(app: FastAPI):
    app.settings = settings

    if settings.app_id_filename:
        with open(settings.app_id_filename, "r") as handle:
            app_id = handle.read()
    else:
        app_id = settings.created_app_id

    if settings.public_key_filename:
        with open(settings.public_key_filename, "r") as handle:
            public_key = handle.read()
    else:
        public_key = settings.created_app_public_key

    app.login_url = f"{settings.hostname}/login/{app_id}"
    app.refresh_url = f"{settings.hostname}/exchange"
    app.key_pair_type = settings.key_pair_type
    app.public_key = public_key

    if isinstance(app.public_key, str):
        app.public_key = app.public_key.encode("utf-8")

    yield


app = FastAPI(lifespan=lifespan)

app = add_exception_handlers(app)

app.include_router(login_app)
app.include_router(admin_app, prefix="/admin")
app.include_router(app_manager_app, prefix="/apps")
