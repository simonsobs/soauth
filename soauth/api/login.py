"""
Main login flow - redirection to GitHub and handling of responses.
"""

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from soauth.service import app as app_service
from soauth.service import github as github_service
from soauth.service import login as login_service

from .dependencies import DatabaseDependency, SettingsDependency

login_router = APIRouter()


@login_router.get("/login/{app_id}")
async def login(
    app_id: uuid.uuid7,
    request: Request,
    settings: SettingsDependency,
    conn: DatabaseDependency,
) -> RedirectResponse:
    try:
        app = await app_service.read_by_id(uid=app_id, conn=conn)
    except app_service.AppNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"App {app_id} not found")

    login_request = await login_service.create(
        app=app, redirect_to=request.headers.get("Referer", None), conn=conn
    )

    redirect_url = await github_service.github_login_redirect(
        login_request=login_request, settings=settings
    )

    return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)


