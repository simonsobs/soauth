"""
Applications/TLDs accessible from the auth server.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class App(SQLModel):
    uid: int = Field(primary_key=True)

    created_by: int = Field()  # Foreign key into users
    created_at: datetime

    domain: str

    method: str
    # Note that the 'public key' is not really public - it should
    # only be shared with the application, as it can be used to decode
    # the signed JWTs.
    public_key: bytes
    private_key: bytes
