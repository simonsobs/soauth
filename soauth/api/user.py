"""
User-facing APIs.
"""

from fastapi import APIRouter, Request

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
        return "No access token found"

    app_id = app_id_from_signed_payload(access_token)
    app = await app_service.read_by_id(app_id, conn=conn)

    try:
        payload = await reconstruct_payload(
            webtoken=access_token,
            public_key=app.public_key,
            key_pair_type=app.key_pair_type,
        )
    except KeyDecodeError:
        return "Access token invalid/expired"

    return f"Hello, {payload['username']}"
