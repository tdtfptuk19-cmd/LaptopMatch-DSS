"""
telemetry.py - POST /api/events, POST /api/feedback, GET /api/rar/stats, GET /api/explain/{offer_id}
"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from laptopmatch_dss.data_subsystem.db import get_db
from laptopmatch_dss.data_subsystem.models import TelemetryEvent, UserFeedback
from laptopmatch_dss.model_subsystem.scoring import DSSScoringEngine, load_persona
from laptopmatch_dss.knowledge_subsystem.explanation import DecisionExplainer
from laptopmatch_dss.api.schemas import (
    TelemetryEventRequest, TelemetryEventResponse,
    UserFeedbackRequest, UserFeedbackResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Telemetry & Feedback"])

explainer = DecisionExplainer()

@router.post("/events", response_model=TelemetryEventResponse, summary="Ghi nhận sự kiện người dùng (đo lường RAR)")
@router.post("/telemetry", response_model=TelemetryEventResponse, summary="Ghi nhận sự kiện telemetry (alias)")
def record_telemetry(req: TelemetryEventRequest, db: Session = Depends(get_db)):
    """
    Ghi nhận hành vi tương tác của người dùng:
    - view_seller: Click sang website nhà bán
    - save_laptop: Lưu máy vào danh sách ưa thích
    - copy_config: Sao chép cấu hình
    - pin_compare: Ghim để so sánh
    Phục vụ trực tiếp cho Khuyến nghị R6: Đo lường Recommendation Acceptance Rate (RAR).
    """
    try:
        event = TelemetryEvent(
            event_type=req.event_type,
            offer_id=req.offer_id,
            persona=req.persona,
            payload_json=json.dumps(req.payload or {}, ensure_ascii=False)
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        logger.info(f"Đã ghi nhận Telemetry event #{event.event_id}: {req.event_type} (offer={req.offer_id})")
        return TelemetryEventResponse(
            status="recorded",
            event_id=event.event_id,
            message="Sự kiện telemetry đã được lưu thành công."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Lỗi lưu telemetry: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feedback", response_model=UserFeedbackResponse, summary="Ghi nhận đánh giá phản hồi từ người dùng")
def record_feedback(req: UserFeedbackRequest, db: Session = Depends(get_db)):
    """Ghi nhận đánh giá tính hữu ích (Có/Không), số sao và góp ý để cải tiến DSS."""
    try:
        feedback = UserFeedback(
            offer_id=req.offer_id,
            persona=req.persona,
            is_helpful=req.is_helpful,
            rating=req.rating,
            comments=req.comments
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        logger.info(f"Đã ghi nhận User Feedback #{feedback.feedback_id}: helpful={req.is_helpful}")
        return UserFeedbackResponse(
            status="recorded",
            feedback_id=feedback.feedback_id,
            message="Đánh giá phản hồi đã được lưu thành công."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Lỗi lưu feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/explain/{offer_id}", summary="Giải thích quyết định đề xuất thông minh bằng AI & Luật chuyên gia")
def explain_offer_decision(offer_id: str, persona_id: str = "Q1", db: Session = Depends(get_db)):
    """
    Sinh lời giải thích tự nhiên bằng tiếng Việt (3-4 câu) cho offer:
    - Phân tích sự thỏa mãn tiêu chuẩn phần cứng (Utility)
    - Phân tích mức độ hời và tiết kiệm tài chính (Deal & Fair Price)
    - Kích hoạt các luật chuyên gia (R1-R6) và phân tích điểm mạnh / điểm đánh đổi
    """
    engine = DSSScoringEngine(db=db)
    try:
        persona = load_persona(persona_id)
        df = engine.get_offers_dataframe(snapshot_date="2026-10-08")
        evaluated = engine.evaluate(persona, df)

        target_matches = evaluated[evaluated["offer_id"] == offer_id]
        if len(target_matches) == 0:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy offer {offer_id}")

        target_row = target_matches.iloc[0].to_dict()

        brand = target_row.get("brand")
        model = target_row.get("model")
        same_model_offers = df[(df["brand"] == brand) & (df["model"] == model)]
        market_ctx = {
            "has_multiple_sellers": bool(len(same_model_offers) > 1),
            "sellers_count": int(len(same_model_offers)),
            "seller_price_diff_vnd": float(same_model_offers["price_vnd"].max() - same_model_offers["price_vnd"].min()) if len(same_model_offers) > 1 else 0.0,
            "cheapest_seller": str(same_model_offers.sort_values("price_vnd").iloc[0]["seller_name"]) if len(same_model_offers) > 1 else ""
        }

        explanation = explainer.explain(target_row, persona, market_context=market_ctx)
        return {
            "offer_id": offer_id,
            "persona_id": persona_id,
            "persona_name": persona.get("name", persona_id),
            "model_info": f"{target_row.get('brand')} {target_row.get('model')} @ {target_row.get('seller_name')}",
            "dss_score": round(float(target_row.get("dss_score", 0.0)), 4),
            "rank": int(target_row.get("rank")) if str(target_row.get("rank")) != "nan" else None,
            "explanation": explanation
        }
    finally:
        engine.close()

@router.get("/rar/stats", summary="Chỉ số Đo lường Tỷ lệ Chấp nhận Khuyến nghị (RAR - R6)")
@router.get("/kpi/rar", summary="Chỉ số RAR (alias)")
def get_recommendation_acceptance_kpi(db: Session = Depends(get_db)):
    """
    Tính toán chỉ số RAR dựa trên hành vi tương tác thực tế từ Telemetry và Feedback.
    """
    total_events = db.query(TelemetryEvent).count()
    view_seller_count = db.query(TelemetryEvent).filter(TelemetryEvent.event_type == "view_seller").count()
    save_laptop_count = db.query(TelemetryEvent).filter(TelemetryEvent.event_type == "save_laptop").count()
    copy_config_count = db.query(TelemetryEvent).filter(TelemetryEvent.event_type == "copy_config").count()
    pin_compare_count = db.query(TelemetryEvent).filter(TelemetryEvent.event_type == "pin_compare").count()

    feedbacks = db.query(UserFeedback).all()
    total_feedbacks = len(feedbacks)
    helpful_feedbacks = sum(1 for f in feedbacks if f.is_helpful)
    helpful_pct = round(helpful_feedbacks / total_feedbacks * 100.0, 1) if total_feedbacks > 0 else None
    avg_rating = round(sum(f.rating for f in feedbacks if f.rating) / sum(1 for f in feedbacks if f.rating), 2) if any(f.rating for f in feedbacks) else None

    rar_click_through = round(view_seller_count / total_events * 100.0, 1) if total_events > 0 else 0.0

    return {
        "status": "active_monitoring",
        "total_telemetry_events": total_events,
        "event_breakdown": {
            "view_seller": view_seller_count,
            "save_laptop": save_laptop_count,
            "copy_config": copy_config_count,
            "pin_compare": pin_compare_count
        },
        "recommendation_acceptance_rate_pct": rar_click_through,
        "user_feedback_summary": {
            "total_reviews": total_feedbacks,
            "helpful_pct": helpful_pct,
            "average_rating_stars": avg_rating
        },
        "note": "Hệ thống đang tích cực ghi nhận snapshot hành vi người dùng theo khuyến nghị R6."
    }
