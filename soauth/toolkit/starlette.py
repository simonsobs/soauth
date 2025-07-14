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

You may also need to add appropriate endpoints for the `handle_redirect` and
`logout` functions defined in this file. The `handle_redirect` handles the case
where the authentication service comes back to you with the keys to set as
cookies, and `logout` handles the case of revoking a user's access token.

There is a global setup function that can be used defined in the `fastapi.py`
file, for FastAPI services.
"""

import json

import httpx
from pydantic import BaseModel, Field
from starlette import status
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
)
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse
from structlog import get_logger

from soauth.core.auth import KeyDecodeError, decode_access_token
from soauth.core.models import KeyRefreshResponse
from soauth.core.tokens import KeyExpiredError
from soauth.core.uuid import UUID


class AuthenticationDecodeError(AuthenticationError):
    pass


class AuthenticationExpiredError(AuthenticationError):
    pass


class SOUser(BaseModel):
    """
    A Simons Observatory user that can be used with the SO Auth backend.
    """

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
    access_token_name: str = "access_token"
    refresh_token_name: str = "refresh_token"

    def __init__(
        self,
        public_key: str | bytes,
        key_pair_type: str,
        access_token_name: str = "access_token",
        refresh_token_name: str = "refresh_token",
    ):
        self.public_key = public_key
        self.key_pair_type = key_pair_type
        self.access_token_name = access_token_name
        self.refresh_token_name = refresh_token_name

    async def authenticate(self, conn: Request):
        log = get_logger()

        log = log.bind(
            client=conn.client,
            access_token_name=self.access_token_name,
            refresh_token_name=self.refresh_token_name,
        )

        # Two possibilities: either we have the access token as a cookie, or we
        # have it as a 'Bearer' token in the headers.

        if "Authorization" in conn.headers:
            contents = conn.headers["Authorization"].split(" ")
            if contents[0] != "Bearer":
                log.debug("tk.starlette.auth.bearer_not_found")
                raise AuthenticationDecodeError("Bearer token invalid")
            log.debug("tk.starlette.auth.bearer")
            access_token = contents[1]
        elif self.access_token_name in conn.cookies:
            log.debug("tk.starlette.auth.access_token_in_cookies")
            access_token = conn.cookies[self.access_token_name]
        else:
            if self.refresh_token_name in conn.cookies:
                log.debug("tk.starlette.auth.only_refresh_cookie")
                raise AuthenticationExpiredError("Token expired")

            log.debug("tk.starlette.auth.no_cookies")
            return AuthCredentials([]), SOUser(
                is_authenticated=False, display_name=None
            )

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
            groups=user_data.group_names,
        )

        log = log.bind(**user.model_dump())

        credentials = AuthCredentials(user_data.grants)

        log = log.bind(grants=user_data.grants)
        log.debug("tk.starlette.auth.success")

        return credentials, user


class MockSOAuthCookieBackend(AuthenticationBackend):
    """
    A mock authentication middleware backend. Always returns an SOUser
    with the provided credentials. This can raise two main
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
    in the FastAPI file (`key_decode_handler` and `key_expired_handler`). You
    can use the `on_auth_error` function to handle all these simultaneously.
    """

    credentials: list[str]
    user_name: str
    user_id: UUID
    full_name: str
    email: str
    groups: set[str]

    def __init__(
        self,
        credentials: list[str],
        user_name: str = "test_user",
        user_id: UUID = UUID("00000000-0000-0000-0000-000000000001"),
        full_name: str = "Test User",
        email: str = "test@test.com",
        groups: set[str] = {"test_user"},
    ):
        self.credentials = credentials
        self.user_name = user_name
        self.user_id = user_id
        self.full_name = full_name
        self.email = email
        self.groups = groups

    async def authenticate(self, conn: Request):
        user = SOUser(
            is_authenticated=True,
            display_name=self.user_name,
            user_id=self.user_id,
            full_name=self.full_name,
            email=self.email,
            groups=self.groups,
        )

        credentials = AuthCredentials(self.credentials)

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

    refresh_token_name = getattr(request.app, "refresh_token_name", "refresh_token")
    access_token_name = getattr(request.app, "access_token_name", "access_token")

    refresh_key = request.cookies[refresh_token_name]

    log = get_logger()
    log = log.bind(
        orginal_url=request.url,
        refresh_token_name=refresh_token_name,
        access_token_name=access_token_name,
    )

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

            response.delete_cookie(access_token_name)
            response.delete_cookie(refresh_token_name)
            return response

        if response.status_code != 200:
            log = log.bind(status_code=response.status_code, content=response.json())
            log.info("tk.starlette.expired.cannot_refresh_key")

            # Best thing we can do is send them back where they came from, and make them run
            # the login flow again.
            response = RedirectResponse(request.url, status_code=302)

            response.delete_cookie(access_token_name)
            response.delete_cookie(refresh_token_name)
            return response

        content = KeyRefreshResponse.model_validate_json(response.content)

    response = RedirectResponse(request.url, status_code=302)

    response.set_cookie(
        access_token_name,
        content.access_token,
        httponly=True,
        expires=content.access_token_expires,
    )
    response.set_cookie(
        refresh_token_name,
        content.refresh_token,
        httponly=True,
        expires=content.refresh_token_expires,
    )

    response.set_cookie(
        key="valid_refresh_token",
        value="True",
        expires=content.refresh_token_expires,
        httponly=False,
    )

    response.set_cookie(
        key="validate_access_token",
        value="True",
        expires=content.access_token_expires,
        httponly=False,
    )

    response.set_cookie(
        key="profile_data",
        value=json.dumps(content.profile_data),
        expires=content.access_token_expires,
        httponly=False,
    )

    log.info("tk.starlette.expired.refreshed")

    return response


def key_decode_handler(request: Request, exc: KeyDecodeError) -> RedirectResponse:
    """
    Handles the KeyDecodeError exception that occurs when the authentication
    process breaks down.

    You MUST provide `request.app.login_url` in your application through
    the lifecycle handlers.
    """

    refresh_token_name = getattr(request.app, "refresh_token_name", "refresh_token")
    access_token_name = getattr(request.app, "access_token_name", "access_token")

    log = get_logger()
    log = log.bind(
        orginal_url=request.url,
        refresh_token_name=refresh_token_name,
        access_token_name=access_token_name,
    )

    response = RedirectResponse(url=request.app.login_url, status_code=302)

    log = log.bind(redirect_to=request.app.login_url)

    response.delete_cookie(access_token_name)
    response.delete_cookie(refresh_token_name)
    response.delete_cookie("valid_refresh_token")
    response.delete_cookie("validate_access_token")
    response.delete_cookie("profile_data")

    log.info("tk.starlette.decode.redirecting")

    return response


def unauthorized_handler(request: Request, exc: HTTPException) -> RedirectResponse:
    """
    Handles any chosen HTTPException by redirecting users to the login.
    """

    return RedirectResponse(url=request.app.login_url, status_code=302)


def on_auth_error(request: Request, exc: Exception):
    if isinstance(exc, AuthenticationDecodeError):
        return key_decode_handler(request=request, exc=exc)
    elif isinstance(exc, AuthenticationExpiredError):
        return key_expired_handler(request=request, exc=exc)
    else:
        # By default, let's just redirect them and delete their cookies.
        return key_expired_handler(request=request, exc=exc)


async def handle_redirect(code: str, state: str, request: Request) -> RedirectResponse:
    """
    Handle the code exchange from the main authentication service. You
    will need to provide an endpoint that takes both `code` and `state`
    GET parameters.

    You must set `request.app.code_url` as the URL to request the code
    exchange for, and also the value `request.app.client_secret` which is
    used in the code exchange.

    Parameters
    ----------
    code: str
        The code recieved as a GET parameter (called code).
    state: str
        The state recieved as a GET parameter (called state), not used.
    request: Request
        The underlying request.

    Raises
    ------
    HTTPException
        With status 401 if the code exchange fails.
    """

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                request.app.code_url,
                params=dict(code=code, secret=request.app.client_secret),
            )

            response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Code exchange failed"
        )

    content = KeyRefreshResponse.model_validate_json(response.content)

    response = RedirectResponse(url=content.redirect, status_code=302)

    refresh_token_name = getattr(request.app, "refresh_token_name", "refresh_token")
    access_token_name = getattr(request.app, "access_token_name", "access_token")

    response.set_cookie(
        key=access_token_name,
        value=content.access_token,
        expires=content.access_token_expires,
        httponly=True,
    )
    response.set_cookie(
        key=refresh_token_name,
        value=content.refresh_token,
        expires=content.refresh_token_expires,
        httponly=True,
    )

    response.set_cookie(
        key="valid_refresh_token",
        value="True",
        expires=content.refresh_token_expires,
        httponly=False,
    )

    response.set_cookie(
        key="validate_access_token",
        value="True",
        expires=content.access_token_expires,
        httponly=False,
    )

    response.set_cookie(
        key="profile_data",
        value=json.dumps(content.profile_data),
        expires=content.access_token_expires,
        httponly=False,
    )

    return response


async def logout(request: Request) -> RedirectResponse:
    """
    Handle the case where a user wants to log out. Uses their own
    cookie to call up the authentication server to expire the token.

    Requires you to set `request.app.base_url` (users are redirected to
    the root once they are logged out) and `request.app.expire_url`, which
    is the main authentication service's expiration endpoint.

    Parameters
    ----------
    request: Request
        The request to the logout endpoint you define.
    """
    response = RedirectResponse(url=request.app.base_url)

    refresh_token_name = getattr(request.app, "refresh_token_name", "refresh_token")
    access_token_name = getattr(request.app, "access_token_name", "access_token")

    if cookie := request.cookies.get(refresh_token_name, None):
        httpx.post(request.app.expire_url, json={"refresh_token": cookie})

    response.delete_cookie(refresh_token_name)
    response.delete_cookie(access_token_name)
    response.delete_cookie("valid_refresh_token")
    response.delete_cookie("validate_access_token")
    response.delete_cookie("profile_data")
    return response
