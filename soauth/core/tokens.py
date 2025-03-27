"""
Tools for encoding, building, and decoding JWTs.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import jwt

from .cryptography import (
    EncryptionSerializationError,
    UnsupportedEncryptionMethod,
    deserialize_private_key,
    deserialize_public_key,
)


class KeyDecodeError(Exception):
    pass


def match_key_pair_type_to_pyjwt_algorithm(key_pair_type: str) -> str:
    match key_pair_type:
        case "Ed25519":
            algorithm = "EdDSA"
        case _:
            raise UnsupportedEncryptionMethod

    return algorithm


def sign_payload(
    app_id: int,
    key_password: str,
    private_key: bytes,
    key_pair_type: str,
    payload: dict[str, Any],
) -> str:
    """
    Sign a JWT payload; requires decrypting the private key and using it.

    Parameters
    ----------
    app_id
        The application ID to store in the header. Required so that we know
        what key to decode this with on the server side for refresh tokens.
    key_password
        The main password for the keys.
    private_key
        The encrypted private key.
    key_pair_type
        The type of key (e.g. Ed25519).
    payload
        The payload for the JWT to encrpyt.
    """

    key = deserialize_private_key(private_key=private_key, key_password=key_password)
    algorithm = match_key_pair_type_to_pyjwt_algorithm(key_pair_type=key_pair_type)

    encrypted = jwt.encode(
        payload=payload, key=key, algorithm=algorithm, headers={"aid": app_id}
    )

    return encrypted


def app_id_from_signed_payload(webtoken: str | bytes) -> int:
    """
    Retrieve the App ID from the web token without deserializing it completely.

    Note: there is **no verification that this token was emitted from a truthful
    source during this process**, that takes place later when reconstructing the
    full payload. But you may need to use this in cases where you have multiple
    keys to choose from.
    """

    header = jwt.get_unverified_header(webtoken)

    try:
        code = int(header["aid"])
    except Exception:
        raise KeyDecodeError("Error reconstructing unverified header")

    return code


def reconstruct_payload(
    webtoken: str | bytes, public_key: bytes, key_pair_type: str
) -> dict[str, Any]:
    """
    Reconstruct a JWT payload; requires reconstituting the public key and using it.

    Paramaters
    ----------
    public_key
        The serialized public key.
    key_pair_type
        The type of key (e.g. Ed25519).
    """

    try:
        key = deserialize_public_key(public_key=public_key)
        algorithm = match_key_pair_type_to_pyjwt_algorithm(key_pair_type=key_pair_type)

        payload = jwt.decode(
            jwt=webtoken,
            key=key,
            algorithms=[algorithm],
        )
    except (jwt.DecodeError, EncryptionSerializationError):
        raise KeyDecodeError("Unable to deserialize content")

    return payload


def build_payload_with_claims(
    base_payload: dict[str, Any],
    expiration_time: datetime,
    valid_from: datetime | None,
    issuer: str | None | list[str],
    audience: str | None | list[str],
) -> dict[str, Any]:
    for a in ("exp", "nbf", "iss", "aud", "iat", "uuid"):
        if a in base_payload:
            raise ValueError(f"Base payload cannot contain key {a}")

    current_time = datetime.now()

    payload = {
        "exp": expiration_time,
        "nbf": valid_from if valid_from is not None else current_time,
        "iat": current_time,
        "uuid": str(uuid.uuid4()),
        **base_payload,
    }

    if issuer is not None:
        payload["iss"] = issuer
    if audience is not None:
        payload["aud"] = audience

    return payload


def build_refresh_key_payload(
    user_id: int, app_id: int, validity: timedelta
) -> dict[str, Any]:
    """
    Builds the payload for a refresh key.
    """

    base_payload = {
        "user_id": user_id,
        "app_id": app_id,
    }

    current_time = datetime.now()

    expiration_time = current_time + validity
    valid_from = current_time

    return build_payload_with_claims(
        base_payload=base_payload,
        expiration_time=expiration_time,
        valid_from=valid_from,
        issuer=None,
        audience=None,
    )


def refresh_refresh_key_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Updates the refresh key payload by:

    - Adding a new uuid
    - Updating valid from and not before.
    """

    new_payload = {**payload}

    current_time = datetime.now()

    new_payload["iat"] = current_time
    new_payload["nbf"] = current_time
    new_payload["uuid"] = str(uuid.uuid4())

    return new_payload
