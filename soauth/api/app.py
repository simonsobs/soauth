"""
FastAPI app
"""

from importlib.metadata import version

from fastapi import FastAPI
from sqlalchemy.exc import IntegrityError

from soauth.service.user import UserExistsError
from soauth.service.user import create as create_user
from soauth.toolkit.fastapi import add_exception_handlers

from .admin import admin_routes
from .app_manager import app_management_routes
from .dependencies import DATABASE_MANAGER, SETTINGS, logger
from .docs import create_protected_docs
from .groups import group_app
from .keys import key_management_routes
from .login import login_app

settings = SETTINGS()


async def lifespan(app: FastAPI):
    app.settings = settings
    app_id = None
    if settings.app_id_filename:
        try:
            with open(settings.app_id_filename, "r") as handle:
                app_id = handle.read()
        except FileNotFoundError:
            raise RuntimeError(f"App ID file not found: {settings.app_id_filename}")
    else:
        app_id = settings.created_app_id
    if not app_id:
        raise RuntimeError("App ID could not be determined.")
    app.app_id = str(app_id)

    if settings.public_key_filename:
        with open(settings.public_key_filename, "r") as handle:
            public_key = handle.read()
    else:
        public_key = settings.created_app_public_key

    app.login_url = f"{settings.hostname}/login/{app_id}"
    app.refresh_url = f"{settings.hostname}/exchange"
    app.key_pair_type = settings.key_pair_type
    app.public_key = public_key

    if isinstance(app.public_key, str):
        app.public_key = app.public_key.encode("utf-8")

    # Ensure that the groups for the app are created
    for organization in settings.github_organization_checks:
        try:
            async with DATABASE_MANAGER.session() as session:
                async with session.begin():
                    await create_user(
                        user_name=organization,
                        email="",
                        full_name=organization,
                        grants=organization,
                        conn=session,
                        log=logger(),
                    )
        except (UserExistsError, IntegrityError):
            pass

    yield


# Set docs to None because they are added later in create_protected_docs
app = FastAPI(
    lifespan=lifespan,
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
    title="SOAuth API",
    summary="API endpoints for the SOAuth service, allowing users to generate access and refresh tokens for accesssing Simons Observatory data services.",
    version=version("soauth"),
)

app = add_exception_handlers(app)
app = create_protected_docs(app)

app.include_router(login_app)
app.include_router(admin_routes, prefix="/admin")
app.include_router(app_management_routes, prefix="/apps")
app.include_router(key_management_routes, prefix="/keys")
app.include_router(group_app, prefix="/groups")
