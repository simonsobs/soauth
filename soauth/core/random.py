"""
Generate random tokens
"""

import secrets


def auth_code():
    return secrets.token_urlsafe(32)


def client_secret():
    return secrets.token_urlsafe(64)
