"""
whatif.py - POST /api/what-if and /api/whatif endpoints
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from laptopmatch_dss.data_subsystem.db import get_db
from laptopmatch_dss.model_subsystem.whatif import WhatIfEngine
from laptopmatch_dss.model_subsystem.scoring import load_persona
from laptopmatch_dss.api.schemas import WhatIfRequest, WhatIfResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["What-If Simulation"])

@router.post("/what-if", response_model=WhatIfResponse, summary="Mô phỏng phân tích kịch bản What-If (WS1-WS5 & Custom)")
@router.post("/whatif", response_model=WhatIfResponse, summary="Mô phỏng kịch bản What-If (alias)")
def run_whatif_scenario(req: WhatIfRequest, db: Session = Depends(get_db)):
    """
    Chạy các kịch bản What-if:
    - WS1: Thắt chặt ngân sách (30tr -> 20tr -> 18tr)
    - WS2: Gaming / Đồ họa
    - WS3: SAZO giảm giá Zenbook AI 7 350
    - WS4: Ràng buộc di động cứng
    - WS5: Hệ sinh thái Apple
    - Custom: Tùy biến mọi tham số
    """
    whatif = WhatIfEngine(db=db)
    try:
        scenario = req.scenario_type.upper() if req.scenario_type else "CUSTOM"

        if scenario == "WS1":
            res = whatif.run_ws1_budget_tightening()
            return WhatIfResponse(
                scenario=res["scenario"],
                findings=res["findings"],
                recommendation=res.get("recommendation"),
                details=res["details"]
            )
        elif scenario == "WS2":
            res = whatif.run_ws2_gaming_shift()
            return WhatIfResponse(
                scenario=res["scenario"],
                findings=res["findings"],
                details=res["details"]
            )
        elif scenario == "WS3":
            cuts = [0.0, 5.0, req.discount_cut_pct or 6.9, 10.0, 15.0]
            res = whatif.run_ws3_price_discount(discount_pcts=cuts)
            return WhatIfResponse(
                scenario=res["scenario"],
                findings=res["findings"],
                details=res["simulation_steps"]
            )
        elif scenario == "WS4":
            res = whatif.run_ws4_portability_constraint()
            return WhatIfResponse(
                scenario=res["scenario"],
                findings=res["findings"],
                details=res["details"]
            )
        elif scenario == "WS5":
            res = whatif.run_ws5_apple_ecosystem()
            return WhatIfResponse(
                scenario=res["scenario"],
                findings=f"{res['findings_27tr']} | {res['findings_36tr']}",
                details={"apple_27tr": res["details_27tr"], "apple_36tr": res["details_36tr"]}
            )
        else: # Custom
            persona = load_persona(req.persona_id)
            if req.budget is not None:
                persona["budget"] = float(req.budget)
            if req.alpha is not None:
                persona["alpha"] = float(req.alpha)
            if req.weights:
                persona["w"] = req.weights
            if req.hard_constraints is not None:
                persona["hard"] = [tuple(h) for h in req.hard_constraints]

            kpi = whatif.simulate_custom(persona, seller_id=req.seller_id, brand=req.brand)
            return WhatIfResponse(
                scenario="Custom What-if Simulation",
                findings=f"Có {kpi['eligible_count']} lựa chọn đạt yêu cầu.",
                comparison_kpi={
                    "avg_utility": kpi["avg_utility"],
                    "avg_price_adv": kpi["avg_price_adv"],
                    "avg_savings_vnd": kpi["avg_savings_vnd"]
                },
                details=kpi
            )
    finally:
        whatif.close()
