"""
FastAPI app
"""

from fastapi import FastAPI

from soauth.toolkit.fastapi import add_exception_handlers

from .admin import admin_app
from .dependencies import SETTINGS
from .login import login_app

settings = SETTINGS()


async def lifespan(app: FastAPI):
    app.settings = settings
    app.login_url = f"http://localhost:8000/login/{settings.created_app_id}"
    app.refresh_url = "http://localhost:8000/exchange"
    app.key_pair_type = settings.key_pair_type
    app.public_key = settings.created_app_public_key

    yield


app = FastAPI(lifespan=lifespan)

app = add_exception_handlers(app)

app.include_router(login_app)
app.include_router(admin_app, prefix="/admin")
