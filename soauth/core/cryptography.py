"""
Cryptography primitives
"""

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    Encoding,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)


class UnsupportedEncryptionMethod(Exception):
    pass


class EncryptionSerializationError(Exception):
    pass


def generate_key_pair(key_pair_type: str, key_password: str) -> tuple[bytes]:
    """
    Generate a public/private key pair.

    Parameters
    ----------
    key_pair_type
        The key pair type to use, currently only Ed25519 is supported.
    key_password
        The key password to encrypt the keys using.

    Returns
    -------
    public_key: bytes
        The public key, serialized to bytes.
    private_key: bytes
        The private key, serialized to (encrypted) bytes.
    """

    match key_pair_type:
        case "Ed25519":
            private = Ed25519PrivateKey.generate()
        case _:
            raise UnsupportedEncryptionMethod

    encryption = BestAvailableEncryption(password=key_password.encode("utf-8"))
    private_key = private.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )
    public_key = private.public_key().public_bytes(
        encoding=Encoding.PEM, format=PublicFormat.SubjectPublicKeyInfo
    )

    return public_key, private_key


def deserialize_private_key(private_key: bytes, key_password: str) -> str:
    try:
        return load_pem_private_key(
            data=private_key, password=key_password.encode("utf-8")
        )
    except (ValueError, UnsupportedAlgorithm):
        raise EncryptionSerializationError("Unable to reconstruct private key")


def deserialize_public_key(public_key: bytes) -> str:
    try:
        return load_pem_public_key(
            data=public_key,
        )
    except (ValueError, UnsupportedAlgorithm):
        raise EncryptionSerializationError("Unable to reconstruct public key")
