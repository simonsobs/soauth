"""
Handlers for GitHub new and returning user flows.

When a user is 'logged in' with GitHub, a new refresh token
is minted and _all others_ are expired. We may have to revisit
that point later.
"""

import urllib
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from soauth.config.settings import Settings
from soauth.database.login import LoginRequest
from soauth.database.user import User
from soauth.service.user import UserNotFound, read_by_name
from soauth.service.user import create as create_user


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
            if item["login"] == organization:
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

    return user


async def github_login(
    code: str, settings: Settings, conn: AsyncSession, log: FilteringBoundLogger
) -> User:
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
    log: FilteringBoundLogger
        Logger

    Returns
    -------
    user: User
        The previously reconstructed or new user.
    """

    login_error = GitHubLoginError("Could not authenticate with GitHub")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "redirect_uri": settings.github_redirect_uri,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )

    log = log.bind(status_code=response.status_code)

    if response.status_code != 200:
        log = log.bind(content=response.json())
        await log.aerror("github.login.code_exchange_failed")
        raise login_error

    gh_access_token = response.json().get("access_token")
    gh_last_logged_in = datetime.now(timezone.utc)

    if gh_access_token is None:
        await log.aerror("github.login.no_access_token")
        raise login_error

    await log.ainfo("github.login.code_exchange_success")

    # Attain user info.
    user_info = await github_api_call(
        github_api_access_token=gh_access_token, url="https://api.github.com/user"
    )

    # Attain organization info
    organization_info = await github_api_call(
        github_api_access_token=gh_access_token, url=user_info["organizations_url"]
    )

    username = user_info["login"].lower()

    log = log.bind(
        user_name=username, email=user_info["email"], full_name=user_info["name"]
    )

    # TODO: call the /email endpoint if email is null using     access token: https://stackoverflow.com/questions/35373995/github-user-email-is-null-despite-useremail-scope
    # TODO: handle no name better? They might not have ever s   za  et one.
    user_email = user_info["email"]

    if user_email is None:
        try:
            user_email_info = await github_api_call(
                github_api_access_token=gh_access_token,
                url="https://api.github.com/user/emails",
            )
            for email in user_email_info:
                if email["primary"]:
                    user_email = email["email"]
                    break
        except GitHubLoginError:
            # I give up...
            user_email = None

    try:
        user = await read_by_name(user_name=username, conn=conn)
        user.email = user_email
        user.full_name = user_info["name"]
        log = log.bind(user_read=True, user_created=False)
    except UserNotFound:
        user = await create_user(
            user_name=username,
            email=user_email,
            full_name=user_info["name"],
            grants="",
            conn=conn,
            log=log,
        )
        log = log.bind(user_created=True, user_read=False)

    log.bind(user_id=user.user_id)

    user.gh_access_token = gh_access_token
    user.gh_last_logged_in = gh_last_logged_in

    log.bind(gh_last_logged_in=gh_last_logged_in)

    user = apply_organization_grants(
        organization_info=organization_info, user=user, settings=settings
    )

    log.bind(grants=user.grants)

    conn.add(user)

    await log.ainfo("github.login.success")

    return user


async def github_login_redirect(login_request: LoginRequest, settings: Settings) -> str:
    """
    Create a redirect to the GitHub App to authenticate a user.
    """

    method = "https"
    host = "github.com"
    endpoint = "login/oauth/authorize"
    query = {
        "client_id": settings.github_client_id,
        "state": str(login_request.login_request_id),
        "scope": "read:user user:email read:org",
    }

    url = urllib.parse.urlunparse(
        (method, host, endpoint, "", urllib.parse.urlencode(query), "")
    )

    return url
