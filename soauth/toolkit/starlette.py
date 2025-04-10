"""
Starlette Authentication Middleware. Also used for FastAPI.

You use this middleware, you will need to first ensure that

- `login_url`, the login redirect for your specific application
- `refresh`, the POST endpoint for refreshing keys for the soauth service

are available as 'global' variables on your app. For instance in FastAPI:

async def lifespan(app: FastAPI):
    app.login_url=f"http://localhost:8000/login/{settings.created_app_id}"
    app.refresh_url="http://localhost:8000/refresh"
    yield

Then add the middleware as follows:

from soauth.toolkit.starlette import SOAuthCookieBackend, on_auth_error
from starlette.middleware.authentication import AuthenticationMiddleware

app.add_middleware(
    AuthenticationMiddleware,
    backend=SOAuthCookieBackend(
        public_key=settings.created_app_public_key,
        key_pair_type=settings.key_pair_type,
    ),
    on_error=on_auth_error
)
"""

import httpx
from pydantic import BaseModel, Field
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
)
from starlette.requests import Request
from starlette.responses import RedirectResponse
from structlog import get_logger

from soauth.core.auth import KeyDecodeError, decode_access_token
from soauth.core.tokens import KeyExpiredError
from soauth.core.uuid import UUID


class AuthenticationDecodeError(AuthenticationError):
    pass


class AuthenticationExpiredError(AuthenticationError):
    pass


class SOUser(BaseModel):
    is_authenticated: bool = False
    display_name: str | None = None
    user_id: UUID | None = None
    full_name: str | None = None
    email: str | None = None
    groups: set[str] = Field(default_factory=set)


class SOAuthCookieBackend(AuthenticationBackend):
    """
    Core authentication middleware backend. This can raise two main
    exceptions:

    soauth.core.tokens.KeyDecodeError
        If there was a problem decoding the access token. This likely
        means that it is incompatible with the keys or otherwise needs
        to be _entirely replaced_ including a new refresh token. You
        should redirect users to the login URL.

    AuthenticationExpiredError
        If the access token key is expired. You will need to use the
        POST endpoint to refresh the key and attempt to re-authenticate.

    To handle these exceptions, we provide synchronous functions defined
    in the FastAPI file (`key_decode_handler` and `key_expired_handler`). You can use
    the `on_auth_error` function to handle all these simultaneously.
    """

    public_key: str | bytes
    key_pair_type: str

    def __init__(
        self,
        public_key: str | bytes,
        key_pair_type: str,
    ):
        self.public_key = public_key
        self.key_pair_type = key_pair_type

    async def authenticate(self, conn: Request):
        log = get_logger()

        log = log.bind(client=conn.client)

        if "access_token" not in conn.cookies:
            log.debug("tk.starlette.auth.no_cookies")
            return AuthCredentials([]), SOUser(
                is_authenticated=False, display_name=None
            )

        access_token = conn.cookies["access_token"]

        if access_token is None:
            log.debug("tk.starlette.auth.no_token")
            raise AuthenticationExpiredError

        try:
            user_data = decode_access_token(
                encrypted_access_token=access_token,
                public_key=self.public_key,
                key_pair_type=self.key_pair_type,
            )
        except KeyDecodeError:
            log.debug("tk.starlette.auth.no_decode")
            raise AuthenticationDecodeError("Could not decode token")
        except KeyExpiredError:
            log.debug("tk.starlette.auth.expired")
            raise AuthenticationExpiredError("Token expired")

        user = SOUser(
            is_authenticated=True,
            display_name=user_data.user_name,
            user_id=user_data.user_id,
            full_name=user_data.full_name,
            email=user_data.email,
            groups=user_data.groups,
        )

        log = log.bind(**user.model_dump())

        credentials = AuthCredentials(user_data.grants)

        log = log.bind(grants=user_data.grants)
        log.debug("tk.starlette.auth.success")

        return credentials, user


def key_expired_handler(request: Request, exc: KeyExpiredError) -> RedirectResponse:
    """
    Handles the KeyExpiredError exception that occurs when the authentication
    key needs to be refreshed.

    You MUST provide `request.app.refresh_key_url` in your application through
    the lifecycle handlers.

    Raises
    ------
    KeyDecodeError
        If there was any problem with the refresh process. Go get a new refresh
        key from a fresh login!
    """

    refresh_key = request.cookies["refresh_token"]

    log = get_logger()
    log = log.bind(orginal_url=request.url)

    if refresh_key is None:
        log.info("tk.starlette.expired.no_token")
        raise KeyDecodeError("You do not have a refresh token, go get one!")

    with httpx.Client() as client:
        log = log.bind(refresh_key_url=request.app.refresh_url)
        try:
            response = client.post(
                request.app.refresh_url, json={"refresh_token": refresh_key}
            )
        except httpx.ReadTimeout:
            log.info("tk.starlette.expired.refresh_timeout")

            # Best thing we can do is send them back where they came from, and make them run
            # the login flow again.
            response = RedirectResponse(request.url, status_code=302)

            response.delete_cookie("access_token")
            response.delete_cookie("refresh_token")
            return response

        if response.status_code != 200:
            log = log.bind(status_code=response.status_code, content=response.json())
            log.info("tk.starlette.expired.cannot_refresh_key")

            # Best thing we can do is send them back where they came from, and make them run
            # the login flow again.
            response = RedirectResponse(request.url, status_code=302)

            response.delete_cookie("access_token")
            response.delete_cookie("refresh_token")
            return response

        content = response.json()

    response = RedirectResponse(request.url, status_code=302)

    response.set_cookie("access_token", content["access_token"])
    response.set_cookie("refresh_token", content["refresh_token"])

    log.info("tk.starlette.expired.refreshed")

    return response


def key_decode_handler(request: Request, exc: KeyDecodeError) -> RedirectResponse:
    """
    Handles the KeyDecodeError exception that occurs when the authentication
    process breaks down.

    You MUST provide `request.app.login_url` in your application through
    the lifecycle handlers.
    """

    log = get_logger()
    log = log.bind(orginal_url=request.url)

    response = RedirectResponse(url=request.app.login_url, status_code=302)

    log = log.bind(redirect_to=request.app.login_url)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    log.info("tk.starlette.decode.redirecting")

    return response


def on_auth_error(request: Request, exc: Exception):
    if isinstance(exc, AuthenticationDecodeError):
        return key_decode_handler(request=request, exc=exc)
    elif isinstance(exc, AuthenticationExpiredError):
        return key_expired_handler(request=request, exc=exc)
    else:
        # By default, let's just redirect them and delete their cookies.
        return key_expired_handler(request=request, exc=exc)
