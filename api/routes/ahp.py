"""
ahp.py - POST /api/ahp/weights and /api/ahp/calculate endpoints
"""
import logging
import numpy as np
from fastapi import APIRouter, HTTPException

from laptopmatch_dss.model_subsystem.ahp import AHPAnalyzer
from laptopmatch_dss.api.schemas import AHPRequest, AHPResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AHP Multi-Criteria"])

@router.post("/ahp/weights", response_model=AHPResponse, summary="Tính trọng số ưu tiên bằng ma trận so sánh cặp AHP")
@router.post("/ahp/calculate", response_model=AHPResponse, summary="Tính trọng số AHP (alias)")
def calculate_ahp(req: AHPRequest):
    """
    Tiếp nhận ma trận so sánh cặp theo thang Saaty 1-9.
    Tính toán vector trọng số w_k, chỉ số CI, CR.
    Nếu CR >= 0.10 sẽ trả về cảnh báo và gợi ý cặp tiêu chí cần điều chỉnh.
    """
    analyzer = AHPAnalyzer(criteria=req.criteria)
    matrix = np.array(req.matrix, dtype=float)

    try:
        res = analyzer.calculate_weights(matrix, criteria=req.criteria, method=req.method or "eigen")
        return AHPResponse(
            is_consistent=res["is_consistent"],
            consistency_ratio=res["consistency_ratio"],
            consistency_index=res["consistency_index"],
            lambda_max=res["lambda_max"],
            weights=res["weights"],
            warning=res["warning"],
            inconsistency_hints=res.get("inconsistency_hints", [])
        )
    except Exception as e:
        logger.error(f"Lỗi tính toán AHP: {e}")
        raise HTTPException(status_code=400, detail=str(e))
