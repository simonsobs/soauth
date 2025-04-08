"""
Test the primary and secondary authentication flows.
"""

import pytest

import soauth.service.app as app_service
import soauth.service.flow as flow_service
import soauth.service.user as user_service


@pytest.mark.asyncio(loop_scope="session")
async def test_primary(user, app, logger, server_settings, session_manager):
    async with session_manager.session() as conn:
        async with conn.begin():
            auth, refresh = await flow_service.primary(
                user=await user_service.read_by_id(user_id=user, conn=conn),
                app=await app_service.read_by_id(app_id=app, conn=conn),
                settings=server_settings,
                conn=conn,
                log=logger,
            )
