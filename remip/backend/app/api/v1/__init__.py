from fastapi import APIRouter

from app.api.v1 import admin, auth, geo, listings, market, notifications, sources, watchlists
from app.api.v1 import map as map_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(geo.router)
api_router.include_router(listings.router)
api_router.include_router(map_router.router)
api_router.include_router(market.router)
api_router.include_router(watchlists.router)
api_router.include_router(notifications.router)
api_router.include_router(sources.router)
api_router.include_router(admin.router)
