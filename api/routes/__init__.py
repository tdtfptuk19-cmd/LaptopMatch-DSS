"""
api/routes package - Aggregated routes for LaptopMatch DSS
"""
from fastapi import APIRouter

from laptopmatch_dss.api.routes.health import router as health_router, pricing_model
from laptopmatch_dss.api.routes.recommend import router as recommend_router
from laptopmatch_dss.api.routes.offers import router as offers_router
from laptopmatch_dss.api.routes.whatif import router as whatif_router
from laptopmatch_dss.api.routes.ahp import router as ahp_router
from laptopmatch_dss.api.routes.telemetry import router as telemetry_router

router = APIRouter(prefix="/api")

router.include_router(health_router)
router.include_router(recommend_router)
router.include_router(offers_router)
router.include_router(whatif_router)
router.include_router(ahp_router)
router.include_router(telemetry_router)

__all__ = ["router", "pricing_model"]
