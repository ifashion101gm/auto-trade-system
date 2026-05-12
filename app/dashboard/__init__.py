"""
Dashboard module - API views and endpoints.
API endpoints as presentation layer for dashboard/UI consumption.
"""
from app.dashboard.trading_api import router as trading_router
from app.dashboard.ai_api import router as ai_router
from app.dashboard.cache_api import router as cache_router
from app.dashboard.llm_api import router as llm_router

__all__ = ['trading_router', 'ai_router', 'cache_router', 'llm_router']
