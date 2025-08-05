"""
A small web server that hosts only one endpoint: /introspect. This processes an
identity token and checks whether the user has the correct grant to be
authenticated against the service. We provide a courtesy '/login' endpoint
that is a small HTML page with a button that directs users to the login page
to
"""

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic_settings import BaseSettings, SettingsConfigDict

from soauth.core.uuid import UUID
from soauth.toolkit.fastapi import global_setup


class ConsumerSettings(BaseSettings):
    app_base_url: str
    authentication_base_url: str
    app_id: UUID
    client_secret: str
    public_key: str
    key_pair_type: str

    required_grant: str = "grant:you_must_choose_one"

    model_config = SettingsConfigDict(env_prefix="SOAUTH_", env_file=".env")


settings = ConsumerSettings()

app = global_setup(
    app=FastAPI(),
    app_base_url=settings.app_base_url,
    authentication_base_url=settings.authentication_base_url,
    app_id=settings.app_id,
    client_secret=settings.client_secret,
    public_key=settings.public_key,
    key_pair_type=settings.key_pair_type,
    handle_exceptions=False,
    use_refresh_token=False,
)


@app.get("/login")
def login(request: Request):
    if request.user.is_authenticated:
        return HTMLResponse(
            content=f"<html><body><a href='{app.logout_url}'>Logout</a>"
        )
    else:
        return HTMLResponse(content=f"<html><body><a href='{app.login_url}'>Login</a>")


@app.post("/introspect")
def introspect(request: Request):
    if not request.user.is_authenticated:
        print("Not authenticated")
        raise HTTPException(401, "Not authenticated")

    if settings.required_grant not in request.auth.scopes:
        print(settings.required_grant, "not in", request.auth.scopes)
        raise HTTPException(401, "Not authorized")
    return Response()
