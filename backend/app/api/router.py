from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.commerce import router as commerce_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.me import router as me_router
from app.api.routes.operator import router as operator_router
from app.api.routes.pet_assets import router as pet_assets_router
from app.api.routes.pet_health import router as pet_health_router
from app.api.routes.pet_life import router as pet_life_router
from app.api.routes.privacy import router as privacy_router
from app.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(commerce_router)
api_router.include_router(knowledge_router)
api_router.include_router(me_router)
api_router.include_router(operator_router)
api_router.include_router(pet_assets_router)
api_router.include_router(pet_health_router)
api_router.include_router(pet_life_router)
api_router.include_router(privacy_router)
api_router.include_router(system_router)
