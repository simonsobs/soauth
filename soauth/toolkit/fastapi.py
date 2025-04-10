"""
Tools for downstream services that can be used to authenticate
users with the service.
"""

import httpx
from fastapi import Request
from fastapi.responses import RedirectResponse

from soauth.core.tokens import KeyDecodeError, KeyExpiredError


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

    if refresh_key is None:
        raise KeyDecodeError("You do not have a refresh token, go get one!")

    with httpx.Client() as client:
        response = client.post(
            request.app.refresh_key_url, data={"refresh_key": refresh_key}
        )

        if response.status_code != 200:
            raise KeyDecodeError("Unable to refresh key!")

        content = response.json()

    response = RedirectResponse(request.url, status_code=302)

    response.set_cookie("access_token", content["access_token"])
    response.set_cookie("refresh_token", content["refresh_token"])

    return response


def key_decode_handler(request: Request, exc: KeyDecodeError) -> RedirectResponse:
    """
    Handles the KeyDecodeError exception that occurs when the authentication
    process breaks down.

    You MUST provide `request.app.login_url` in your application through
    the lifecycle handlers.
    """

    response = RedirectResponse(url=request.app.login_url, status_code=302)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return response
