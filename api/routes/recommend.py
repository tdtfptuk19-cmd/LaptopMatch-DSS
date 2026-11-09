"""
recommend.py - POST /api/recommend endpoint
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from laptopmatch_dss.data_subsystem.db import get_db
from laptopmatch_dss.model_subsystem.scoring import DSSScoringEngine, load_persona
from laptopmatch_dss.api.schemas import RecommendRequest, RecommendResponse, OfferResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Recommendation"])

@router.post("/recommend", response_model=RecommendResponse, summary="Gợi ý danh sách laptop tối ưu theo DSS_Score")
def recommend_laptops(req: RecommendRequest, db: Session = Depends(get_db)):
    """
    Tính điểm DSS_Score = Eligibility x [alpha*Utility + (1-alpha)*Deal].
    Cung cấp thông tin chi tiết từng tiêu chí S_k, Shop_Trust và cảnh báo đắt >= 10%.
    """
    engine = DSSScoringEngine(db=db)
    try:
        # 1. Xác định Persona cơ sở
        persona = load_persona(req.persona_id) if req.persona_id else load_persona("Q1")
        persona_name = persona.get("name", req.persona_id or "Custom Profile")

        # 2. Ghi đè tham số nếu người dùng tùy chỉnh
        if req.budget is not None:
            persona["budget"] = float(req.budget)
        if req.alpha is not None:
            persona["alpha"] = float(req.alpha)
        if req.k is not None:
            persona["k"] = float(req.k)
        if req.weights:
            persona["w"] = req.weights
        if req.thresholds:
            persona["r"] = req.thresholds
        if req.hard_constraints is not None:
            persona["hard"] = [tuple(h) for h in req.hard_constraints]

        # 3. Lấy dữ liệu và áp dụng bộ lọc nguồn nếu có
        df = engine.get_offers_dataframe(snapshot_date="2026-10-08")
        total_market = len(df)

        if req.seller_id:
            df = df[df["seller_id"] == req.seller_id]
        if req.brand:
            df = df[df["brand"].str.upper() == req.brand.upper()]

        # 4. Đánh giá đa tiêu chí
        evaluated_df = engine.evaluate(persona, df)
        eligible_df = evaluated_df[evaluated_df["eligible"] == 1]
        total_eligible = len(eligible_df)

        # 5. Định dạng kết quả Top-N
        top_list = eligible_df.head(req.top_n)
        offers_out = []

        for _, r in top_list.iterrows():
            criteria_scores = {}
            for k in persona.get("w", {}).keys():
                col_name = "S_" + k
                if col_name in r:
                    criteria_scores[k] = round(float(r[col_name]), 4)

            adv_pct = round(float(r["price_adv"]), 2)
            expensive_warning = bool(adv_pct <= -10.0)

            offers_out.append(OfferResponse(
                rank=int(r["rank"]),
                offer_id=r["offer_id"],
                brand=r["brand"],
                model=r["model"],
                seller_id=r["seller_id"],
                seller_name=r["seller_name"],
                city=r["city"],
                price_vnd=float(r["price_vnd"]),
                price_m=round(float(r["price_vnd"]) / 1e6, 2),
                fair_price_vnd=float(r["fair_price"]),
                price_adv_pct=adv_pct,
                utility=round(float(r["utility"]), 4),
                deal=round(float(r["deal"]), 4),
                dss_score=round(float(r["dss_score"]), 4),
                shop_trust=round(float(r["shop_trust"]), 4),
                warranty_months=int(r["warranty_months"]),
                return_days=int(r["return_days"]),
                ram_gb=int(r["ram_gb"]),
                ssd_gb=int(r["ssd_gb"]),
                weight_kg=float(r["weight_kg"]),
                battery_wh=float(r["battery_wh"]),
                expensive_warning=expensive_warning,
                criteria_scores=criteria_scores
            ))

        # 6. Thống kê KPI tổng quan
        avg_utility = round(float(top_list["utility"].mean()), 3) if len(top_list) > 0 else 0.0
        avg_adv = round(float(top_list["price_adv"].mean()), 1) if len(top_list) > 0 else 0.0
        avg_savings = round(float((top_list["fair_price"] - top_list["price_vnd"]).mean()), 0) if len(top_list) > 0 else 0.0

        return RecommendResponse(
            persona_used=persona_name,
            total_eligible=total_eligible,
            total_market_offers=total_market,
            top_offers=offers_out,
            summary_kpi={
                "top1_dss_score": offers_out[0].dss_score if offers_out else 0.0,
                "top1_model": f"{offers_out[0].brand} {offers_out[0].model} @ {offers_out[0].seller_name}" if offers_out else "None",
                "avg_utility_top5": avg_utility,
                "avg_price_advantage_pct": avg_adv,
                "avg_savings_vnd": avg_savings,
                "violation_rate_pct": 0.0
            }
        )
    finally:
        engine.close()
