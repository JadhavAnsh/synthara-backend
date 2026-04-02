"""Route modules for the Synthara backend API."""

from app.api.routes.health import router as health_router
from app.api.routes.root import router as root_router

__all__ = ["health_router", "root_router"]
