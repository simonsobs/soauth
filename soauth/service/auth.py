"""
Creation/deletion for authentication keys.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from soauth.config.settings import Settings
from soauth.core.tokens import build_payload_with_claims, sign_payload
from soauth.database.app import App
from soauth.database.auth import RefreshKey
from soauth.database.user import User


async def create_auth_key(
    refresh_key: RefreshKey, settings: Settings, conn: AsyncSession
) -> tuple[str, datetime]:
    """
    This function **assumes it is being passed a valid refresh key** and
    creates an authentication key for the user associated with it.

    Returned is the packaged and encrypted data.
    """

    with conn.no_autoflush:
        user = await conn.get(User, refresh_key.user_id, populate_existing=True)

    app = await conn.get(App, refresh_key.app_id)

    user_data = user.to_core()
    base_payload = user_data.model_dump()

    current_time = datetime.now(timezone.utc)
    expiration_time = current_time + settings.access_key_expiry

    payload = build_payload_with_claims(
        base_payload=base_payload,
        expiration_time=expiration_time,
        valid_from=None,
        issuer=None,
        audience=None,
    )

    signed_payload = sign_payload(
        app_id=app.app_id,
        key_password=settings.key_password,
        private_key=app.private_key,
        key_pair_type=app.key_pair_type,
        payload=payload,
    )

    refresh_key.used += 1

    user.last_access_token = payload["uuid"]
    user.last_access_time = payload["iat"]
    user.number_of_access_tokens += 1

    conn.add_all([refresh_key, user])

    return signed_payload, expiration_time
