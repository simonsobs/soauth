"""
User-facing APIs.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from soauth.core.tokens import (
    KeyDecodeError,
    app_id_from_signed_payload,
    reconstruct_payload,
)
from soauth.core.uuid import UUID
from soauth.database.app import App
from soauth.service import app as app_service
from soauth.service import flow as flow_service

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

    access_token = request.cookies.get("access_token", None)

    if access_token is None:
        only_app = (await conn.execute(select(App))).scalar_one()
        login = f"<a href='/login/{only_app.app_id}'>Login</a>"
        return HTMLResponse(f"No access token found, login? {login}")

    try:
        app_id = UUID(int=app_id_from_signed_payload(access_token))
        log = log.bind(app_id=app_id)
        app = await app_service.read_by_id(app_id, conn=conn)
    except app_service.AppNotFound:
        await log.ainfo("api.request.home.app_not_found")
        await flow_service.logout(
            encoded_refresh_key=request.cookies.get("refresh_token", ""),
            settings=settings,
            conn=conn,
            log=log,
        )
        response = RedirectResponse("/")
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        return response

    try:
        payload = reconstruct_payload(
            webtoken=access_token,
            public_key=app.public_key,
            key_pair_type=app.key_pair_type,
        )
    except KeyDecodeError:
        return HTMLResponse("Access token invalid/expired")

    if "simonsobs" in payload["grants"]:
        proprietary = "<p>Congratulations, you have access to proprietary data!</p><img src='https://upload.wikimedia.org/wikipedia/en/1/1f/Pokémon_Charizard_art.png' />"
    else:
        proprietary = ""

    return HTMLResponse(
        f"<h1>Hello, {payload['full_name']} ({payload['user_name']})</h1>{proprietary}"
    )
