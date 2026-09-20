"""API routes."""

from fastapi import APIRouter

from app.api import auth, dashboard, documents, incidents

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["Incidents"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
