"""
Tools for downstream services that can be used to authenticate
users with the service.

To use this endpoint, you will need to have set:

- `login_url`, the login redirect for your specific application
- `refresh`, the POST endpoint for refreshing keys for the soauth service
- `public_key`, the public key component for your application
- `key_pair_type`, the key pair type for your application

on your application through the lifecycle handler.

You should also call `add_exception_handlers` on your app at startup,
lest you return a bunch of 500s when access tokens are invalid.

If you are looking for a one-stop-shop, check out `global_setup`.

To use the dependency:

```
from soauth.toolkit.fastapi import UserDependency

@app.get("/endpoint")
async def endpoint(user: UserDependency):
    if not user.is_authenticated:
        return

# Raises a 401 HTTPException if not `user.is_authenticated`
@app.get("/completely_secure")
async def secure_endpoint(user: AuthenticatedUserDependency):
    assert user.is_authenticated
```
"""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import Field
from starlette.middleware.authentication import AuthenticationMiddleware
from structlog import get_logger

from soauth.core.auth import KeyDecodeError, decode_access_token
from soauth.core.tokens import KeyExpiredError
from soauth.core.uuid import UUID

from .starlette import (
    MockSOAuthCookieBackend,
    SOAuthCookieBackend,
    SOUser,
    handle_redirect,
    key_decode_handler,
    key_expired_handler,
    logout,
    on_auth_error,
)


class SOUserWithGrants(SOUser):
    grants: set[str] = Field(default_factory=set)


def add_exception_handlers(app: FastAPI) -> FastAPI:
    """
    Adds exception handlers for authentication. To use these, you must:

    - Set `app.login_url` to the GET URL for your application on the main authentication
      service. This will look like `{auth_service_domain}/login/{your_app_id}`
    - Set `app.refresh_url` to the POST URL for the main authentication service for
      refreshing keys. This will look like `{auth_service_domain}/exchange`

    Optionally, you can:

    - Set `app.refresh_token_name` to change the cookie name for the refresh token
    - Set `app.access_token_name` to change the cookie name for the access token
    """
    app.add_exception_handler(KeyDecodeError, key_decode_handler)
    app.add_exception_handler(KeyExpiredError, key_expired_handler)
    return app


async def handle_user(request: Request) -> SOUserWithGrants:
    """
    Handler for user authentication. To handles the cases where we
    have a decode or expiry error, you should call the `add_exception_handlers`
    function on your app.

    You will _always_ be returned an `SOUserWithGrants`. You should check
    whether or not it `is_authenticated`. Unlike the starlette implementation,
    grants (or 'credentials' as they are known there) are included in the user
    model to keep everything self-contained.

    To use this, and all others, you will need to set:

    - `request.app.public_key` to the public key for your application.
    - `request.app.key_pair_type` to the public key type for your application.
    """

    refresh_token_name = getattr(request.app, "refresh_token_name", "refresh_token")
    access_token_name = getattr(request.app, "access_token_name", "access_token")

    log = get_logger()

    log = log.bind(
        client=request.client,
        refresh_token_name=refresh_token_name,
        access_token_name=access_token_name,
    )

    # Two possibilities: either we have the access token as a cookie, or we
    # have it as a 'Bearer' token in the headers.

    if "Authorization" in request.headers:
        contents = request.headers["Authorization"].split(" ")
        if contents[0] != "Bearer":
            raise KeyDecodeError
        access_token = contents[1]
    elif access_token_name in request.cookies:
        access_token = request.cookies[access_token_name]
    else:
        log.debug("tk.fastapi.auth.no_token")
        return SOUserWithGrants(is_authenticated=False)

    if access_token is None:
        log.debug("tk.fastapi.auth.no_token")
        raise KeyDecodeError("Invalid value for access token")

    try:
        user_data = decode_access_token(
            encrypted_access_token=access_token,
            public_key=request.app.public_key,
            key_pair_type=request.app.key_pair_type,
        )
    except KeyDecodeError as e:
        log.debug("tk.fastapi.auth.no_decode")
        raise e
    except KeyExpiredError as e:
        log.debug("tk.fastapi.auth.expired")
        raise e

    user = SOUserWithGrants(
        is_authenticated=True,
        display_name=user_data.user_name,
        user_id=user_data.user_id,
        full_name=user_data.full_name,
        email=user_data.email,
        groups=user_data.group_names,
        grants=user_data.grants,
    )

    log = log.bind(**user.model_dump())

    log.debug("tk.fastapi.auth.success")

    return user


async def handle_authenticated_user(request: Request) -> SOUserWithGrants:
    """
    The same as `handle_user` but raises a 401 if the user is not
    authenticated. Check `handle_user` for requirements.
    """
    user = await handle_user(request=request)

    if not user.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Log in first"
        )

    return user


def global_setup(
    app: FastAPI,
    app_base_url: str,
    authentication_base_url: str,
    app_id: str | UUID,
    client_secret: str,
    public_key: str,
    key_pair_type: str,
    add_middleware: bool = True,
) -> FastAPI:
    """
    Transform the app such that it is ready for authentication. Can either add middleware
    (the default) or simply set up the application such that it is ready for use with the
    dependencies defined in this file (e.g. `UserDependency` and `AuthenticatedUserDependency`)

    Parameters
    ----------
    app: FastAPI
        The FastAPI app to hook into.
    app_base_url: str
        The base URL for your application. Example: https://www.simonsobs.org, or
        https://nersc.simonsobs.org/beta/simple.
    authentication_base_url: str
        The base URL for the authentication service to use.
    app_id: str | UUID
        The UUID of your app as registered with the authentication service.
    client_secret: str
        The client secret provided by the authentication service.
    public_key: str
        The public key provided by the authentication service.
    key_pair_type: str
        The key pair type used for the keys, given by the authentication service.
    add_middleware: bool = True
        Add middleare to your application to automatically authenticate each request.
        This allows for the use of starlette's `@requries()` (against user grants), and
        access to `request.user` and `request.auth.scopes`. Alternatively, you can use
        the dependencies defined in this file.

    Example
    -------

    Your `.env` file or set of environment variables:

    ```
    APP_BASE_URL=https://nersc.simonsobs.org/beta/simple
    AUTHENTICATION_BASE_URL=https://identity.simonsobservatory.url
    APP_ID=0680039d-0774-75f1-8000-317277b414eb
    CLIENT_SECRET=w2URATShbumYOoBuiK9VBMsT8tahjVAAuDdJWTdZ5K2TN8h
    PUBLIC_KEY_FILE=/secrets/local_key.pem
    KEY_PAIR_TYPE=Ed25519
    ```

    Then, in the code (using `pydantic_settings` to read these):

    ```python
    from pydantic_settings import BaseSettings
    from fastapi import FastAPI
    from soauth.toolkit.fastapi import global_setup

    class AppSettings(BaseSettings):
        app_base_url: str
        authentication_base_url: str
        app_id: str
        client_secret: str
        public_key_file: str
        key_pair_type: str
        public_key: str | None = None

        def model_post_init(context):
            with open(self.public_key_file, "r") as handle:
                self.public_key = handle.read()

    settings = AppSettings()

    app = global_setup(
        app=FastAPI(),
        app_base_url=settings.app_base_url,
        authentication_base_url=settings.authentication_base_url,
        app_id=settings.app_id,
        client_secret=settings.client_secret,
        key_pair_type=settings.key_pair_type,
        public_key=settings.public_key,
    )
    ```

    Your app is now fully authenticated and endpoints can be protected against individual
    scopes using:

    ```python
    from starlette.authentication import requires

    @app.get("/test")
    @requires("admin")
    async def test(request: Request):
        user = request.user
        scopes = request.auth.scopes
        return {"user": user, "scopes": scopes}
    ```
    """

    app.base_url = app_base_url
    app.authentication_url = authentication_base_url
    app.client_secret = client_secret
    app.app_id = app_id

    app.public_key = public_key.encode("utf-8")
    app.key_pair_type = key_pair_type

    # Derived URLs (set as defaults based on bundled OAuth provider).
    app.login_url = f"{authentication_base_url}/login/{app_id}"
    app.code_url = f"{authentication_base_url}/code/{app_id}"
    app.refresh_url = f"{authentication_base_url}/exchange"
    app.expire_url = f"{authentication_base_url}/expire"
    app.logout_url = f"{app_base_url}/logout"

    if add_middleware:
        app.add_middleware(
            AuthenticationMiddleware,
            backend=SOAuthCookieBackend(
                public_key=app.public_key, key_pair_type=app.key_pair_type
            ),
            on_error=on_auth_error,
        )

    app.add_api_route(path="/logout", endpoint=logout)
    app.add_api_route(path="/callback", endpoint=handle_redirect)

    return app


def mock_global_setup(
    app: FastAPI,
    grants: list[str],
) -> FastAPI:
    """
    Transform the app such that it is ready for authentication (mock).
    Always returns a user 'test_user', with the given grants. Only works
    with middleware, the dependencies will not work.

    Parameters
    ----------
    app: FastAPI
        The FastAPI app to hook into.
    grants: list[str]
        The list of grants to give the user. This is used to mock the
        authentication process, and should be used for testing purposes only.
    """

    app.add_middleware(
        AuthenticationMiddleware,
        backend=MockSOAuthCookieBackend(
            credentials=grants,
        ),
    )

    return app


UserDependency = Annotated[SOUserWithGrants, Depends(handle_user)]
AuthenticatedUserDependency = Annotated[
    SOUserWithGrants, Depends(handle_authenticated_user)
]
