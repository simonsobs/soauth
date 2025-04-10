"""
User-facing APIs.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from soauth.database.app import App

from .dependencies import DatabaseDependency, LoggerDependency, SettingsDependency

user_router = APIRouter()


@user_router.get("/")
async def home(
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
    log: LoggerDependency,
):
    log.debug("api.request.home")

    if not request.user.is_authenticated:
        only_app = (await conn.execute(select(App))).scalar_one()
        login = f"<a href='/login/{only_app.app_id}'>Login</a>"
        return HTMLResponse(f"No access token found, login? {login}")

    # try:
    #     app_id = UUID(hex=app_id_from_signed_payload(access_token))
    #     log = log.bind(app_id=app_id)
    #     app = await app_service.read_by_id(app_id, conn=conn)
    # except app_service.AppNotFound:
    #     await log.ainfo("api.request.home.app_not_found")
    #     await flow_service.logout(
    #         encoded_refresh_key=request.cookies.get("refresh_token", ""),
    #         settings=settings,
    #         conn=conn,
    #         log=log,
    #     )
    #     response = RedirectResponse("/")
    #     response.delete_cookie("access_token")
    #     response.delete_cookie("refresh_token")
    #     return response

    if "simonsobs" in request.auth.scopes:
        proprietary = "<p>Congratulations, you have access to proprietary data!</p><img src='https://upload.wikimedia.org/wikipedia/en/1/1f/Pokémon_Charizard_art.png' />"
    else:
        proprietary = ""

    return HTMLResponse(
        f"<h1>Hello, {request.user.full_name} ({request.user.display_name})</h1>{proprietary}"
    )
