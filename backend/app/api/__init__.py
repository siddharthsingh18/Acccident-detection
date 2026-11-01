from .health import router as health_router
from .incidents import router as incidents_router
from .media import router as media_router
from .websockets import router as websockets_router
from .feeds import router as feeds_router
from .settings import router as settings_router
from .models import router as models_router
from .samples import router as samples_router

__all__ = [
    "health_router",
    "incidents_router",
    "media_router",
    "websockets_router",
    "feeds_router",
    "settings_router",
    "models_router",
    "samples_router",
]
