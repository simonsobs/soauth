"""
One-stop functionality for decoding access tokens
"""

from cachetools import TTLCache, cached
from pydantic import ValidationError

from soauth.core.tokens import KeyDecodeError, reconstruct_payload
from soauth.core.user import UserData


@cached(cache=TTLCache(maxsize=256, ttl=600))
def decode_access_token(
    encrypted_access_token: str | bytes, public_key: str | bytes, key_pair_type: str
) -> UserData:
    """
    Raises
    ------
    KeyDecodeError
        When there is a problem decoding the key
    KeyExpiredError
        When the key has expired
    """

    payload = reconstruct_payload(
        webtoken=encrypted_access_token,
        public_key=public_key,
        key_pair_type=key_pair_type,
    )

    try:
        return UserData.model_validate(payload)
    except ValidationError:
        raise KeyDecodeError("Error reconstructing the user model")
