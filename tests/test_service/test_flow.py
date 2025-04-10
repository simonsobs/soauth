"""
Test the primary and secondary authentication flows.
"""

import pytest

import soauth.service.app as app_service
import soauth.service.flow as flow_service
import soauth.service.user as user_service
from soauth.core.tokens import reconstruct_payload


@pytest.mark.asyncio(loop_scope="session")
async def test_primary_then_secondary(
    user, app, logger, server_settings, session_manager
):
    async with session_manager.session() as conn:
        async with conn.begin():
            application = await app_service.read_by_id(app_id=app, conn=conn)
            user_obj = await user_service.read_by_id(user_id=user, conn=conn)
            auth, refresh = await flow_service.primary(
                user=user_obj,
                app=application,
                settings=server_settings,
                conn=conn,
                log=logger,
            )

            APP_PUBLIC_KEY = application.public_key
            APP_KEY_PAIR_TYPE = application.key_pair_type
            USER_ID = user_obj.user_id

    # Check we can decode it ok!
    decoded_authentication = reconstruct_payload(
        webtoken=auth, public_key=APP_PUBLIC_KEY, key_pair_type=APP_KEY_PAIR_TYPE
    )

    assert decoded_authentication["user_id"] == USER_ID.hex

    # Ok, now let's refresh it!
    async with session_manager.session() as conn:
        async with conn.begin():
            auth, refresh = await flow_service.secondary(
                encoded_refresh_key=refresh,
                settings=server_settings,
                conn=conn,
                log=logger,
            )

    # Check we can decode it ok!
    decoded_authentication = reconstruct_payload(
        webtoken=auth, public_key=APP_PUBLIC_KEY, key_pair_type=APP_KEY_PAIR_TYPE
    )

    assert decoded_authentication["user_id"] == USER_ID.hex

    # Log them out.
    async with session_manager.session() as conn:
        async with conn.begin():
            await flow_service.logout(
                encoded_refresh_key=refresh,
                settings=server_settings,
                conn=conn,
                log=logger,
            )

    raise Exception
