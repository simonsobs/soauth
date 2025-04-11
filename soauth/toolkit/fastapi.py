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

To use the dependency:

from soauth.toolkit.fastapi import UserDependency

@app.get("/endpoint")
async def endpoint(user: UserDependency):
    if not user.is_authenticated:
        return

# Raises a 401 HTTPException if not `user.is_authenticated`
@app.get("/completely_secure")
async def secure_endpoint(user: AuthenticatedUserDependency):
    assert user.is_authenticated

"""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import Field
from structlog import get_logger

from soauth.core.auth import KeyDecodeError, decode_access_token
from soauth.core.tokens import KeyExpiredError

from .starlette import SOUser, key_decode_handler, key_expired_handler


class SOUserWithGrants(SOUser):
    grants: set[str] = Field(default_factory=set)


def add_exception_handlers(app: FastAPI) -> FastAPI:
    """
    Adds exception handlers for authentication
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
    """

    log = get_logger()

    log = log.bind(client=request.client)

    # TODO: What if they have refresh token but not access token?

    if "access_token" not in request.cookies:
        log.debug("tk.fastapi.auth.no_cookies")
        return SOUserWithGrants(is_authenticated=False)

    access_token = request.cookies["access_token"]

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
        groups=user_data.groups,
        grants=user_data.grants,
    )

    log = log.bind(**user.model_dump())

    log.debug("tk.fastapi.auth.success")

    return user


async def handle_authenticated_user(request: Request) -> SOUserWithGrants:
    """
    The same as `handle_user` but raises a 401 if the user is not
    authenticated.
    """
    user = await handle_user(request=request)

    if not user.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Log in first"
        )

    return user


UserDependency = Annotated[SOUserWithGrants, Depends(handle_user)]
AuthenticatedUserDependency = Annotated[
    SOUserWithGrants, Depends(handle_authenticated_user)
]
