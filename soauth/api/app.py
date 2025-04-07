"""
FastAPI app
"""

from fastapi import FastAPI

from .login import login_router
from .user import user_router

app = FastAPI()

app.include_router(user_router)
app.include_router(login_router)
