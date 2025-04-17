from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from .dependencies import LoggerDependency, TemplateDependency


def template_endpoint(
    app: FastAPI,
    path: str,
    template: str,
    context: dict[str, Any] = {},
    methods=["GET"],
    log_name: str | None = None,
):
    def core(request: Request, templates: TemplateDependency, log: LoggerDependency):
        if log_name is not None:
            log.bind(user=request.user, scopes=request.auth.scopes, context=context)
            log.info(log_name)
        return templates.TemplateResponse(
            request=request,
            name=template,
            context=context,
        )

    app.add_api_route(path=path, endpoint=core)


def templateify(template_name: str = None, log_name: str | None = None):
    """
    Apply a template to a route. Your route should return a dictionary
    which is added to the template context. You must have `request: Request`
    and `templates: TemplateDependency` in your kwargs. If log_name is not
    None, you must also have `log: LoggerDependency`.
    """

    def decorator(route: Callable):
        @wraps(route)
        def wrapped(*args, **kwargs):
            context = route(*args, **kwargs)

            if context is None:
                context = {}

            request = kwargs.get("request")
            templates: Jinja2Templates = kwargs.get("templates")

            if log_name is not None:
                log = kwargs.get("log")
                log = log.bind(
                    user=request.user, scopes=request.auth.scopes, context=context
                )
                log.info(log_name)

            return templates.TemplateResponse(
                request=request,
                name=template_name,
                context=context,
            )

        return wrapped

    return decorator
