"""
FastAPI does not support adding dependencies to routes _after_ their creation, so
we must create them ourselves (note that they DO NOT allow overwriting)
"""

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse

from .admin import AdminUser


def create_protected_docs(
    app: FastAPI, openapi_url="/openapi.json", docs_url="/docs", redoc_url="/redoc"
) -> FastAPI:
    async def custom_openapi(request: Request, user: AdminUser):
        return JSONResponse(app.openapi())

    app.add_api_route(
        path=openapi_url,
        endpoint=custom_openapi,
        methods=["GET"],
        include_in_schema=False,
    )

    async def custom_swagger_ui(request: Request, user: AdminUser):
        return get_swagger_ui_html(
            openapi_url=openapi_url, title="Protected Docs (Swagger)"
        )

    app.add_api_route(
        path=docs_url,
        endpoint=custom_swagger_ui,
        methods=["GET"],
        include_in_schema=False,
    )

    async def custom_redoc(request: Request, user: AdminUser):
        return get_redoc_html(openapi_url=openapi_url, title="Protected Docs (Redoc)")

    app.add_api_route(
        path=redoc_url, endpoint=custom_redoc, methods=["GET"], include_in_schema=False
    )

    return app
