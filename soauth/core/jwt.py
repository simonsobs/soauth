"""
Tools for encoding, building, and decoding JWTs.
"""

from typing import Any
from datetime import datetime
from .cryptography import deserialize_private_key, UnsupportedEncryptionMethod, deserialize_public_key

import jwt


def match_key_pair_type_to_pyjwt_algorithm(key_pair_type: str) -> str:
    match key_pair_type:
        case 'Ed25519':
            algorithm = 'EdDSA'
        case _:
            raise UnsupportedEncryptionMethod
        
    return algorithm


def sign_payload(key_password: str, private_key: bytes, key_pair_type: str, payload: dict[str, Any]) -> str:
    """
    Sign a JWT payload; requires decrypting the private key and using it.

    Parameters
    ----------
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
        payload=payload,
        key=key,
        algorithm=algorithm,
    )

    return encrypted


def reconstruct_payload(webtoken: str | bytes, public_key: bytes, key_pair_type: str) -> dict[str, Any]:
    """
    Reconstruct a JWT payload; requires reconstituting the public key and using it.
    
    Paramaters
    ----------
    public_key
        The serialized public key.
    key_pair_type
        The type of key (e.g. Ed25519).
    """

    key = deserialize_public_key(public_key=public_key)
    algorithm = match_key_pair_type_to_pyjwt_algorithm(key_pair_type=key_pair_type)

    payload = jwt.decode(
        jwt=webtoken,
        key=key,
        algorithms=[algorithm],
    )

    return payload


def build_payload_with_claims(base_payload: dict[str, Any], expiration_time: datetime, valid_from: datetime | None, issuer: str | None | list[str], audience: str | None | list[str]):
    for a in ("exp", "nbf", "iss", "aud", "iat"):
        if a in base_payload:
            raise ValueError(
                f"Base payload cannot contain key {a}"
            )
        
    current_time = datetime.now()

    payload = {
        "exp": expiration_time,
        "nbf": valid_from if valid_from is not None else current_time,
        "iat": current_time,
        **base_payload
    }

    if issuer is not None:
        payload["iss"] = issuer
    if audience is not None:
        payload["aud"] = audience

    return payload