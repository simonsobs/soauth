"""
Applications/TLDs accessible from the auth server.
"""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class App(SQLModel):
    app_id: uuid.uuid7 = Field(primary_key=True, default_factory=uuid.uuid7)

    created_by: int = Field()  # Foreign key into users
    created_at: datetime

    domain: str

    key_pair_type: str
    # Note that the 'public key' is not really public - it should
    # only be shared with the application, as it can be used to decode
    # the signed JWTs.
    public_key: bytes
    private_key: bytes
