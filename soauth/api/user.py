"""
User-facing APIs.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from soauth.database.app import App

from .dependencies import (
    SETTINGS,
    DatabaseDependency,
    LoggerDependency,
    SettingsDependency,
)

settings = SETTINGS()

user_app = APIRouter()


@user_app.get("/")
async def home(
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
):
    log.debug("api.request.home")

    if not request.user.is_authenticated:
        only_app = (await conn.execute(select(App))).scalar_one()
        login = f"<a href='login/{only_app.app_id}'>Login</a>"
        return HTMLResponse(f"No access token found, login? {login}")

    if "simonsobs" in request.auth.scopes:
        proprietary = "<p>Congratulations, you have access to proprietary data!</p><img src='https://upload.wikimedia.org/wikipedia/en/1/1f/Pokémon_Charizard_art.png' />"
    else:
        proprietary = ""

    logout = "<p><a href='logout'>Logout</a></p>"

    return HTMLResponse(
        f"<h1>Hello, {request.user.full_name} ({request.user.display_name})</h1>{proprietary}{logout}"
    )
