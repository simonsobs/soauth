"""
User-facing APIs.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from soauth.core.tokens import (
    KeyDecodeError,
    app_id_from_signed_payload,
    reconstruct_payload,
)
from soauth.service import app as app_service

from .dependencies import DatabaseDependency, SettingsDependency

user_router = APIRouter("/")


@user_router.get("/")
async def home(
    request: Request, settings: SettingsDependency, conn: DatabaseDependency
):
    access_token = request.cookies.get("access_token", None)

    if access_token is None:
        return HTMLResponse("No access token found")

    app_id = app_id_from_signed_payload(access_token)
    app = await app_service.read_by_id(app_id, conn=conn)

    try:
        payload = await reconstruct_payload(
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

        

    return HTMLResponse(f"<h1>Hello, {payload['username']}</h1>{proprietary}")
