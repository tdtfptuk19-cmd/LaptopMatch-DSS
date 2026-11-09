"""
health.py - Health check, system status & model info endpoints
"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from laptopmatch_dss.data_subsystem.db import get_db
from laptopmatch_dss.data_subsystem.models import Offer, Seller
from laptopmatch_dss.model_subsystem.pricing import HedonicPricingModel
from laptopmatch_dss.model_subsystem.scoring import load_persona
from laptopmatch_dss.config.settings import PERSONAS_CONFIG_PATH
from laptopmatch_dss.api.schemas import HedonicModelResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health & Models"])

pricing_model = HedonicPricingModel()
pricing_model.load_latest_or_fallback()

@router.get("/health", summary="Kiểm tra trạng thái hệ thống")
def health_check(db: Session = Depends(get_db)):
    """Kiểm tra kết nối CSDL và các thành phần cốt lõi."""
    try:
        seller_count = db.query(Seller).count()
        offer_count = db.query(Offer).count()
        return {
            "status": "healthy",
            "database": "connected",
            "dim_sellers_count": seller_count,
            "fact_offers_count": offer_count,
            "active_model_version": pricing_model.version,
            "model_r2": pricing_model.r_squared,
            "model_mape": pricing_model.mape_5fold
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/model/info", response_model=HedonicModelResponse, summary="Lấy thông số mô hình định giá Hedonic OLS Robust HC3")
@router.get("/models/hedonic", response_model=HedonicModelResponse, summary="Lấy thông số mô hình định giá Hedonic (alias)")
def get_hedonic_model_metadata():
    """
    Trả về 6 hệ số beta, intercept, R2, MAPE (5-fold CV), Breusch-Pagan p-value
    và metadata phiên bản đang hoạt động của mô hình Hedonic.
    """
    if not pricing_model.coefficients:
        pricing_model.load_latest_or_fallback()

    return HedonicModelResponse(
        version=pricing_model.version,
        created_at=getattr(pricing_model, "created_at", "2026-10-08T00:00:00"),
        snapshot_date=pricing_model.snapshot_date or "2026-10-08",
        sample_size=pricing_model.sample_size,
        r_squared=round(pricing_model.r_squared, 4),
        mape_5fold_pct=round(pricing_model.mape_5fold, 2),
        breusch_pagan_pvalue=round(pricing_model.breusch_pagan_pvalue, 5),
        intercept=pricing_model.intercept,
        coefficients=pricing_model.coefficients,
        features=list(pricing_model.coefficients.keys()),
        cov_type="HC3"
    )

@router.get("/personas", summary="Lấy danh sách các Persona mẫu")
def list_personas():
    """Trả về danh sách các Persona có sẵn trong hệ thống (Q1, U1, U2, U4, U5)."""
    if PERSONAS_CONFIG_PATH.exists():
        with open(PERSONAS_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"Q1": load_persona("Q1")}
