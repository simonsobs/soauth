"""
Core 'frontend' app, where users can log in and view/update status.
This does not require any access to the database, and purely uses the
soauth authentication scheme. It is packed purely for simplicity.
"""

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from starlette.middleware.authentication import AuthenticationMiddleware

from soauth.toolkit.starlette import SOAuthCookieBackend, on_auth_error

from .dependencies import LoggerDependency

AUTHENTICATION_SERVICE_URL = "http://localhost:8000"

# Grab the details
with httpx.Client() as client:
    response = client.get(f"{AUTHENTICATION_SERVICE_URL}/developer_details")

    content = response.json()

    app_id = content["authentication_app_id"]
    public_key = content["authentication_public_key"]
    key_type = content["authentication_key_type"]


async def lifespan(app: FastAPI):
    app.login_url = f"{AUTHENTICATION_SERVICE_URL}/login/{app_id}"
    app.logout_url = f"{AUTHENTICATION_SERVICE_URL}/logout"
    app.refresh_url = f"{AUTHENTICATION_SERVICE_URL}/exchange"

    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    AuthenticationMiddleware,
    backend=SOAuthCookieBackend(
        public_key=public_key.encode("utf-8"),
        key_pair_type=key_type,
    ),
    on_error=on_auth_error,
)


@app.get("/")
async def home(
    request: Request,
    log: LoggerDependency,
):
    log.debug("app.request.home")

    if not request.user.is_authenticated:
        login = f"<a href='{request.app.login_url}'>Login</a>"
        return HTMLResponse(f"No access token found, login? {login}")

    if "simonsobs" in request.auth.scopes:
        proprietary = "<p>Congratulations, you have access to proprietary data!</p><img src='https://upload.wikimedia.org/wikipedia/en/1/1f/Pokémon_Charizard_art.png' />"
    else:
        proprietary = ""

    logout = "<p><a href='logout'>Logout</a></p>"

    return HTMLResponse(
        f"<h1>Hello, {request.user.full_name} ({request.user.display_name})</h1>{proprietary}{logout}"
    )
