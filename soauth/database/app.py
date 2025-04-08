"""
Applications/TLDs accessible from the auth server.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from soauth.core.uuid import UUID, uuid7


class App(SQLModel, table=True):
    app_id: UUID = Field(primary_key=True, default_factory=uuid7)

    created_by: int = Field()  # Foreign key into users
    created_at: datetime

    domain: str

    key_pair_type: str
    # Note that the 'public key' is not really public - it should
    # only be shared with the application, as it can be used to decode
    # the signed JWTs.
    public_key: bytes
    private_key: bytes
