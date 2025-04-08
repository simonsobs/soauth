"""
Handlers for GitHub new and returning user flows.

When a user is 'logged in' with GitHub, a new refresh token
is minted and _all others_ are expired. We may have to revisit
that point later.
"""

import urllib
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from soauth.config.settings import Settings
from soauth.database.login import LoginRequest
from soauth.database.user import User
from soauth.service.user import UserNotFound, read_by_name


class GitHubLoginError(Exception):
    pass


async def github_api_call(
    github_api_access_token: str | None, url: str
) -> dict[str, Any]:
    """
    Make an api call to the GitHub APi using your access token.
    """

    headers = {
        "Accept": "application/json",
    }

    if github_api_access_token:
        headers["Authorization"] = f"Bearer {github_api_access_token}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

    if response.status_code != 200:
        raise GitHubLoginError(f"Error contacting {url}")

    return response.json()


def apply_organization_grants(
    organization_info: list[dict[str, any]], user: User, settings: Settings
) -> User:
    """
    Checks whether the user has the correct organization grants given a freshly
    pulled set of organization info from GitHub. If not, we remedy that.
    """

    # Add grants that have the same name as the GitHub organizations that
    # we care about.
    for organization in settings.github_organization_checks:
        org_found = False
        for item in organization_info:
            if item.login == organization:
                org_found = True
                user.add_grant(organization)
                break

        if not org_found:
            user.remove_grant(organization)

    return user


async def github_check_orgs_without_login(
    user: User, settings: Settings, conn: AsyncSession
):
    """
    Runs the organization check without requiring a login (used for the secondary
    flow when we do not want to have to re-authenticate with GitHub).
    """

    organization_info = await github_api_call(
        None, url=f"https://api.github.com/users/{user.user_name}/orgs"
    )

    user = apply_organization_grants(
        organization_info=organization_info, user=user, settings=settings
    )

    conn.add(user)
    await conn.commit()
    await conn.refresh(user)

    return user


async def github_login(code: str, settings: Settings, conn: AsyncSession) -> User:
    """
    Perform the GitHub login _after recieving the code from the GitHub
    authentication service. That code is used to authenticate against
    GitHub and attain a refresh and access token.

    Parameters
    ----------
    code: str
        The code provided by GitHub to authenticate against a user.
    settings
        Server settings, containing our GitHub App auth codes.
    conn: AsyncSession
        Database session

    Returns
    -------
    user: User
        The previously reconstructed or new user.
    """

    login_error = GitHubLoginError("Could not authenticate with GitHub")

    async with httpx.AsyncClient() as client:
        response = client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "redirect_uri": settings.github_redirect_uri,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )

    if response.status_code != 200:
        raise login_error

    gh_access_token = response.json().get("access_token")
    gh_last_logged_in = datetime.now()

    if gh_access_token is None:
        raise login_error

    # Attain user info.
    user_info = await github_api_call(
        github_api_access_token=gh_access_token, url="https://api.github.com/user"
    )

    # Attain organization info
    organization_info = await github_api_call(
        github_api_access_token=gh_access_token, url=user_info["organizations_url"]
    )

    username = user_info["login"]

    try:
        user = await read_by_name(user_name=username, conn=conn)
    except UserNotFound:
        user = User(
            full_name=user_info["name"],
            user_name=username,
            email=user_info["email"],
        )

    user.gh_access_token = gh_access_token
    user.gh_last_logged_in = gh_last_logged_in

    user = apply_organization_grants(
        organization_info=organization_info, user=user, settings=settings
    )

    conn.add(user)
    await conn.commit()
    await conn.refresh(user)

    return user


async def github_login_redirect(login_request: LoginRequest, settings: Settings) -> str:
    """
    Create a redirect to the GitHub App to authenticate a user.
    """

    method = "https"
    host = "github.com"
    endpoint = "login/oauth/autorhize"
    query = {
        "client_id": settings.github_client_id,
        "state": str(login_request.login_request_id),
    }

    url = urllib.parse.urlunparse(
        (method, host, endpoint, "", urllib.parse.urlencode(query))
    )

    return url
