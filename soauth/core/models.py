"""
Pydantic models for request/responses to APIs.
"""

from datetime import datetime

from pydantic import BaseModel

from soauth.core.user import UserData

from .app import AppData, LoggedInUserData


class KeyRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    redirect: str | None = None
    access_token_expires: datetime
    refresh_token_expires: datetime


class APIKeyCreationResponse(BaseModel):
    refresh_token: str
    refresh_token_expires: datetime


class RefreshTokenModel(BaseModel):
    refresh_token: str | bytes


class AppRefreshResponse(BaseModel):
    app: AppData
    public_key: str
    key_pair_type: str
    client_secret: str


class AppDetailResponse(BaseModel):
    app: AppData
    users: list[LoggedInUserData]


class ModifyUserContent(BaseModel):
    grant_add: str | None = None
    grant_remove: str | None = None


class UserDetailResponse(BaseModel):
    user: UserData
    logins: list[LoggedInUserData]
