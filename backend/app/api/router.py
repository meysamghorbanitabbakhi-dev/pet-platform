import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.commerce import router as commerce_router
from app.api.routes.concierge_offers import router as concierge_offers_router
from app.api.routes.customer_requests import router as customer_requests_router
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
api_router.include_router(concierge_offers_router)
api_router.include_router(customer_requests_router)
api_router.include_router(knowledge_router)
api_router.include_router(me_router)
api_router.include_router(operator_router)
_price_intelligence_module_path = (
    Path(__file__).parent / "routes" / "operator" / "price_intelligence.py"
)
_price_intelligence_spec = importlib.util.spec_from_file_location(
    "app.api.routes.operator_price_intelligence",
    _price_intelligence_module_path,
)
if _price_intelligence_spec and _price_intelligence_spec.loader:
    _price_intelligence_module = importlib.util.module_from_spec(_price_intelligence_spec)
    sys.modules[_price_intelligence_spec.name] = _price_intelligence_module
    _price_intelligence_spec.loader.exec_module(_price_intelligence_module)
    if isinstance(_price_intelligence_module, ModuleType):
        price_intelligence_router = _price_intelligence_module.router
        api_router.include_router(price_intelligence_router)
api_router.include_router(pet_assets_router)
api_router.include_router(pet_health_router)
api_router.include_router(pet_life_router)
api_router.include_router(privacy_router)
api_router.include_router(system_router)
