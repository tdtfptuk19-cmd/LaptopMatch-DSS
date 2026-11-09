"""
schemas.py - Định nghĩa Pydantic Schemas cho Backend API
Chuẩn hóa dữ liệu đầu vào và đầu ra cho LaptopMatch DSS.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# --- Schemas cho Khuyến nghị (Recommendation) ---
class HardConstraint(BaseModel):
    field: str
    op: str # '>=', '<=', '==', '!='
    value: Any

class RecommendRequest(BaseModel):
    persona_id: Optional[str] = Field("Q1", description="ID của persona (Q1, U1, U2, U4, U5) hoặc để trống nếu dùng tùy chỉnh")
    budget: Optional[float] = Field(None, description="Ngân sách tối đa (VND), nếu chỉ định sẽ ghi đè persona")
    alpha: Optional[float] = Field(None, ge=0.0, le=1.0, description="Trọng số Utility [0.0, 1.0], còn lại 1-alpha là Deal")
    k: Optional[float] = Field(None, ge=1.0, le=30.0, description="Hệ số dốc Sigmoid cho điểm Deal (mặc định 10.0)")
    weights: Optional[Dict[str, float]] = Field(None, description="Vector trọng số w_k (cpu, ram, ssd, bat, hz, w)")
    thresholds: Optional[Dict[str, float]] = Field(None, description="Ngưỡng kỳ vọng r_k")
    hard_constraints: Optional[List[List[Any]]] = Field(None, description="Danh sách ràng buộc cứng dạng [[field, op, value], ...]")
    seller_id: Optional[str] = Field(None, description="Lọc theo nhà bán cụ thể (FPT, CPS, GEAR, SAZO, T&T Center, NCPC)")
    brand: Optional[str] = Field(None, description="Lọc theo thương hiệu (ASUS, Acer, Lenovo, HP, Dell, Apple, MSI)")
    top_n: int = Field(10, ge=1, le=50, description="Số lượng offer cần lấy")

class OfferResponse(BaseModel):
    rank: int
    offer_id: str
    brand: str
    model: str
    seller_id: str
    seller_name: str
    city: str
    price_vnd: float
    price_m: float
    fair_price_vnd: float
    price_adv_pct: float
    utility: float
    deal: float
    dss_score: float
    shop_trust: float
    warranty_months: int
    return_days: int
    ram_gb: int
    ssd_gb: int
    weight_kg: float
    battery_wh: float
    expensive_warning: bool = Field(False, description="Cảnh báo nếu đắt hơn giá hợp lý >= 10% (Adv <= -10%)")
    criteria_scores: Dict[str, float] = Field(default_factory=dict, description="Điểm thành phần S_k từng tiêu chí")

class RecommendResponse(BaseModel):
    persona_used: str
    total_eligible: int
    total_market_offers: int
    top_offers: List[OfferResponse]
    summary_kpi: Dict[str, Any]

# --- Schemas cho AHP ---
class AHPRequest(BaseModel):
    criteria: List[str] = Field(["cpu", "ram", "ssd", "w"], description="Danh sách các tiêu chí cần so sánh")
    matrix: List[List[float]] = Field(..., description="Ma trận so sánh cặp nxn theo thang Saaty 1-9")
    method: Optional[str] = Field("eigen", description="Phương pháp tính: 'eigen' (Principal Eigenvector) hoặc 'geometric'")

class InconsistencyHint(BaseModel):
    criterion_1: str
    criterion_2: str
    current_judgment: float
    recommended_value: float

class AHPResponse(BaseModel):
    is_consistent: bool
    consistency_ratio: float
    consistency_index: float
    lambda_max: float
    weights: Dict[str, float]
    warning: Optional[str] = None
    inconsistency_hints: List[InconsistencyHint] = []

# --- Schemas cho What-If Simulation ---
class WhatIfRequest(BaseModel):
    scenario_type: Optional[str] = Field(None, description="Preset kịch bản: WS1, WS2, WS3, WS4, WS5 hoặc None/custom")
    persona_id: Optional[str] = Field("Q1", description="Persona cơ sở")
    budget: Optional[float] = Field(None, description="Ngân sách mới")
    alpha: Optional[float] = Field(None, description="Alpha mới")
    weights: Optional[Dict[str, float]] = Field(None, description="Trọng số mới")
    hard_constraints: Optional[List[List[Any]]] = Field(None, description="Ràng buộc cứng mới")
    seller_id: Optional[str] = Field(None, description="Lọc nhà bán")
    brand: Optional[str] = Field(None, description="Lọc thương hiệu")
    discount_cut_pct: Optional[float] = Field(None, description="Mức giảm giá thêm (dành cho WS3)")

class WhatIfResponse(BaseModel):
    scenario: str
    findings: Optional[str] = None
    recommendation: Optional[str] = None
    comparison_kpi: Optional[Dict[str, Any]] = None
    details: Any

# --- Schemas cho Hedonic Model ---
class HedonicModelResponse(BaseModel):
    version: str
    created_at: str
    snapshot_date: str
    sample_size: int
    r_squared: float
    mape_5fold_pct: float
    breusch_pagan_pvalue: float
    intercept: float
    coefficients: Dict[str, float]
    features: List[str]
    cov_type: str = "HC3"

# --- Schemas cho Telemetry & Feedback (Đo lường RAR theo R6) ---
class TelemetryEventRequest(BaseModel):
    event_type: str = Field(..., description="view_seller, save_laptop, copy_config, pin_compare")
    offer_id: Optional[str] = Field(None, description="Mã offer liên quan")
    persona: Optional[str] = Field("Q1", description="Persona đang chọn")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Dữ liệu kèm theo")

class TelemetryEventResponse(BaseModel):
    status: str
    event_id: int
    message: str

class UserFeedbackRequest(BaseModel):
    offer_id: Optional[str] = None
    persona: Optional[str] = "Q1"
    is_helpful: bool = Field(..., description="Khuyến nghị có hữu ích không (True/False)")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Đánh giá sao 1-5")
    comments: Optional[str] = None

class UserFeedbackResponse(BaseModel):
    status: str
    feedback_id: int
    message: str
