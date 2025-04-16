"""
Pydantic models for request/responses to APIs.
"""

from datetime import datetime

from pydantic import BaseModel


class KeyRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    redirect: str | None = None
    access_token_expires: datetime
    refresh_token_expires: datetime


class RefreshTokenModel(BaseModel):
    refresh_token: str | bytes
