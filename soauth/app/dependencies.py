"""
FastAPI dependencies.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from structlog import get_logger
from structlog.typing import FilteringBoundLogger

from soauth.config.settings import Settings


def logger():
    return get_logger()


def setup_templates(settings: Settings):
    def internal_urls(request: Request):
        return dict(
            base_url=f"{settings.management_hostname}{settings.management_path}",
            user_list=f"{settings.management_hostname}{settings.management_path}/users",
            app_list=f"{settings.management_hostname}{settings.management_path}/apps",
            key_list=f"{settings.management_hostname}{settings.management_path}/keys",
            logout_url=f"{settings.management_hostname}{settings.management_path}/logout",
            login_url=f"{settings.hostname}/login/{request.app.app_id}",
            group_list=f"{settings.management_hostname}{settings.management_path}/groups",
        )

    def user_and_scope(request: Request):
        return dict(user=request.user, scopes=request.auth.scopes)

    def extra_functions(request: Request):
        return dict(zip=zip, len=len)

    templates = Jinja2Templates(
        directory=__file__.replace("dependencies.py", "templates"),
        context_processors=[internal_urls, user_and_scope, extra_functions],
    )

    @lru_cache
    def get_templates():
        return templates

    return get_templates


settings = Settings()
get_templates = setup_templates(settings=settings)


LoggerDependency = Annotated[FilteringBoundLogger, Depends(logger)]
TemplateDependency = Annotated[Jinja2Templates, Depends(get_templates)]
