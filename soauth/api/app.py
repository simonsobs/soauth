"""
FastAPI app
"""

from fastapi import FastAPI
from starlette.middleware.authentication import AuthenticationMiddleware

from soauth.toolkit.starlette import SOAuthCookieBackend, on_auth_error

from .dependencies import SETTINGS
from .login import login_router
from .user import user_router

settings = SETTINGS()


async def lifespan(app: FastAPI):
    app.login_url = f"http://localhost:8000/login/{settings.created_app_id}"
    app.refresh_url = "http://localhost:8000/refresh"
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    AuthenticationMiddleware,
    backend=SOAuthCookieBackend(
        public_key=settings.created_app_public_key,
        key_pair_type=settings.key_pair_type,
    ),
    on_error=on_auth_error,
)

app.include_router(user_router)
app.include_router(login_router)
