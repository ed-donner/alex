"""
Routers package exporting controller routers for Alex API.
"""

from .user import router as user_router
from .accounts import router as accounts_router
from .positions import router as positions_router
from .instruments import router as instruments_router
from .test_data import router as test_data_router
from .analysis import router as analysis_router

__all__ = [
    "user_router",
    "accounts_router",
    "positions_router",
    "instruments_router",
    "test_data_router",
    "analysis_router",
]
