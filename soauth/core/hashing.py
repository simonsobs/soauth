"""
Utilities for hashing and comparing hashes.
"""

from __future__ import annotations

import hashlib

import xxhash


class UnsupportedHashAlgorithm(Exception):
    pass


def match_name_to_algorithm(name: str) -> hashlib._Hash:
    match name:
        case "xxh3":
            return xxhash.xxh3_64
        case _:
            raise UnsupportedHashAlgorithm(f"Algorithm {name} not supported")


def checksum(content: str | bytes, hash_algorithm: str) -> str:
    """
    Calclulate a fresh hash (named checksum to avoid colliding with
    internal function hash) of some content. You _must_ provide a valid
    hash_algorithm name (usually grab this from settings.hash_algorithm).
    """
    algorithm = match_name_to_algorithm(hash_algorithm)

    return algorithm(content).hexdigest()


def compare(content: str | bytes, compare_to: str, hash_algorithm: str) -> bool:
    """
    Compare some content (hashed with hash_algorithm) to a pre-existing checksum
    (`compare_to`).
    """
    new_hash = hash(content=content, hash_algorithm=hash_algorithm)

    return compare_to == new_hash
