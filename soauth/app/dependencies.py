"""
FastAPI dependencies.
"""

from typing import Annotated

from fastapi import Depends
from structlog import get_logger
from structlog.typing import FilteringBoundLogger


def logger():
    return get_logger()


LoggerDependency = Annotated[FilteringBoundLogger, Depends(logger)]
