"""
FastAPI app
"""

from fastapi import FastAPI

from .dependencies import SETTINGS
from .login import login_app

settings = SETTINGS()


async def lifespan(app: FastAPI):
    app.settings = settings
    app.login_url = f"http://0.0.0.0:8000/login/{settings.created_app_id}"
    app.refresh_url = "http://0.0.0.0:8000/exchange"

    print(app.login_url)

    yield


app = FastAPI(lifespan=lifespan)

# app.include_router(user_app)
app.include_router(login_app)
