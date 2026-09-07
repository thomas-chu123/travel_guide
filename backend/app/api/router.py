from fastapi import APIRouter

from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.api.routes.locations import router as locations_router
from app.api.routes.supabase import router as supabase_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["system"])
api_router.include_router(events_router, tags=["events"])
api_router.include_router(locations_router, tags=["locations"])
api_router.include_router(supabase_router, tags=["supabase"])
