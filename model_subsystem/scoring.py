"""
scoring.py - Bộ chấm điểm đa tiêu chí DSS (Model Management Subsystem)
Cài đặt chính xác các hàm quyết định từ ASM2:
- Hàm giá trị thành phần S_k(x, r, kind, xmax, xmin)
- Điểm hữu dụng kỹ thuật Utility = sum(w_k * S_k)
- Điểm hời Deal = Sigmoid(k * Price_Adv / 100) * Shop_Trust
- Điều kiện đủ Eligibility (ngân sách, quality_status='pass', ràng buộc cứng)
- Điểm tổng hợp DSS_Score = Eligibility * [alpha * Utility + (1 - alpha) * Deal]
"""
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from laptopmatch_dss.config.settings import MODELS_CONFIG_PATH, PERSONAS_CONFIG_PATH
from laptopmatch_dss.data_subsystem.db import SessionLocal
from laptopmatch_dss.data_subsystem.models import Offer, Laptop, Seller

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Bảng tiêu chí và phân loại (benefit: càng cao càng tốt, cost: càng thấp càng tốt)
CRITERIA_MAP = {
    "cpu": ("cpu_benchmark_score", "benefit", "CPU"),
    "gpu": ("gpu_benchmark_score", "benefit", "GPU"),
    "ram": ("ram_gb", "benefit", "RAM"),
    "ssd": ("ssd_gb", "benefit", "SSD"),
    "bat": ("battery_wh", "benefit", "Pin"),
    "hz": ("refresh_hz", "benefit", "Tần số quét"),
    "w": ("weight_kg", "cost", "Cân nặng"),
}

# Ngưỡng chuẩn hóa min/max trên toàn bộ thị trường T1 (từ models_config.json)
DEFAULT_FEATURE_BOUNDS = {
    "cpu": {"min": 5800.0, "max": 59800.0},
    "gpu": {"min": 1200.0, "max": 41500.0},
    "ram": {"min": 8.0, "max": 64.0},
    "ssd": {"min": 256.0, "max": 3072.0},
    "bat": {"min": 36.0, "max": 99.0},
    "hz": {"min": 60.0, "max": 300.0},
    "w": {"min": 0.99, "max": 3.25},
}

def load_feature_bounds() -> Tuple[Dict[str, float], Dict[str, float]]:
    """Tải XMAX và XMIN từ models_config.json nếu có."""
    if MODELS_CONFIG_PATH.exists():
        try:
            with open(MODELS_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            bounds = cfg.get("feature_bounds", DEFAULT_FEATURE_BOUNDS)
            xmax = {k: float(v["max"]) for k, v in bounds.items()}
            xmin = {k: float(v["min"]) for k, v in bounds.items()}
            return xmax, xmin
        except Exception:
            pass
    xmax = {k: float(v["max"]) for k, v in DEFAULT_FEATURE_BOUNDS.items()}
    xmin = {k: float(v["min"]) for k, v in DEFAULT_FEATURE_BOUNDS.items()}
    return xmax, xmin

XMAX, XMIN = load_feature_bounds()

def S_k(x: np.ndarray, r: float, kind: str, xmax: float, xmin: float) -> np.ndarray:
    """
    Hàm giá trị thành phần cho từng tiêu chí k (chuẩn hóa về [0, 1]):
    - Khi đạt đúng yêu cầu r: đạt 0.7 điểm
    - Với tiêu chí 'benefit' (càng cao càng tốt):
        + x < r: tăng tuyến tính từ 0 đến 0.7: 0.7 * x / r
        + x >= r: thưởng vượt kỳ vọng: 0.7 + 0.3 * (x - r) / (xmax - r)
    - Với tiêu chí 'cost' (càng thấp càng tốt - Cân nặng):
        + x <= r: nhẹ hơn yêu cầu: 0.7 + 0.3 * (r - x) / (r - xmin)
        + x > r: nặng hơn yêu cầu: 0.7 * max(0, 1 - (x - r) / r)
    """
    x = np.asarray(x, dtype=float)
    if kind == "benefit":
        above = 0.7 + 0.3 * (x - r) / (xmax - r) if xmax > r else np.ones_like(x)
        return np.where(x < r, 0.7 * x / r, above)
    else: # cost (cân nặng)
        under = 0.7 + 0.3 * (r - x) / (r - xmin) if r > xmin else np.ones_like(x)
        penalty = 0.7 * np.clip(1.0 - (x - r) / r, 0.0, None)
        return np.where(x <= r, under, penalty)

def sigmoid(z: np.ndarray) -> np.ndarray:
    """Hàm logistic sigmoid chuyển đổi chênh lệch giá thành điểm hời [0, 1]."""
    return 1.0 / (1.0 + np.exp(-np.asarray(z, dtype=float)))

def load_persona(persona_key: str = "Q1") -> Dict[str, Any]:
    """Tải hồ sơ người dùng từ file cấu hình personas_config.json và chuẩn hóa cấu trúc."""
    if PERSONAS_CONFIG_PATH.exists():
        with open(PERSONAS_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if persona_key in cfg:
            raw = cfg[persona_key].copy()
            kz_val = float(raw.get("kz", raw.get("k", 1.5)))
            p = {
                "name": raw.get("name", persona_key),
                "budget": float(raw.get("budget", 30_000_000)),
                "alpha": float(raw.get("alpha", 0.65)),
                "kz": kz_val,
                "k": kz_val,
                "w": raw.get("w", raw.get("weights_w", {})),
                "r": raw.get("r", raw.get("thresholds_r", {})),
            }
            # Chuẩn hóa hard constraints
            hard = []
            if "hard" in raw:
                hard = [tuple(h) if isinstance(h, (list, tuple)) else (h["field"], h["op"], h["value"]) for h in raw["hard"]]
            elif "hard_constraints" in raw:
                hard = [(h["field"], h["op"], h["value"]) for h in raw["hard_constraints"]]
            p["hard"] = hard
            return p

    # Fallback mặc định Q1 (ASM2 v7: 82 offer đạt chuẩn)
    return {
        "name": "Q1 – SV lập trình, <= 30 tr, ưu tiên máy nhẹ",
        "budget": 30_000_000,
        "alpha": 0.65,
        "kz": 1.5,
        "k": 1.5,
        "hard": [("ram_gb", ">=", 16), ("ssd_gb", ">=", 512), ("cpu_benchmark_score", ">=", 18000)],
        "r": {"cpu": 18000, "ram": 16, "ssd": 512, "w": 1.5},
        "w": {"cpu": 0.5 * 0.4615, "ram": 0.5 * 0.4154, "ssd": 0.5 * 0.1231, "w": 0.5}
    }

class DSSScoringEngine:
    """
    Động cơ chấm điểm quyết định LaptopMatch DSS.
    """
    def __init__(self, db: Session = None):
        self.db = db if db else SessionLocal()
        self._owns_db = db is None

    def close(self):
        if self._owns_db and self.db:
            self.db.close()

    def get_offers_dataframe(self, snapshot_date = None) -> pd.DataFrame:
        """Trích xuất danh sách offer kèm thông số máy và nhà bán từ CSDL."""
        query = self.db.query(
            Offer.offer_id,
            Offer.laptop_id,
            Offer.seller_id,
            Seller.seller_name,
            Seller.city,
            Offer.price_vnd,
            Offer.list_price_vnd,
            Offer.discount_pct,
            Offer.warranty_months,
            Offer.return_days,
            Offer.condition,
            Offer.availability,
            Offer.snapshot_date,
            Offer.quality_status,
            Offer.anomaly_flag,
            Offer.fair_price,
            Offer.price_adv,
            Offer.shop_trust,
            Offer.source_url,
            Laptop.brand,
            Laptop.model,
            Laptop.release_year,
            Laptop.cpu,
            Laptop.cpu_benchmark_score,
            Laptop.gpu,
            Laptop.gpu_benchmark_score,
            Laptop.dgpu,
            Laptop.ram_gb,
            Laptop.ssd_gb,
            Laptop.screen_inch,
            Laptop.resolution_width_px,
            Laptop.resolution_height_px,
            Laptop.refresh_hz,
            Laptop.weight_kg,
            Laptop.battery_wh
        ).join(Laptop, Offer.laptop_id == Laptop.laptop_id)\
         .join(Seller, Offer.seller_id == Seller.seller_id)

        if snapshot_date:
            query = query.filter(Offer.snapshot_date == snapshot_date)

        records = query.all()
        data = [{
            "offer_id": r.offer_id,
            "laptop_id": r.laptop_id,
            "seller_id": r.seller_id,
            "seller_name": r.seller_name,
            "city": r.city,
            "brand": r.brand,
            "model": r.model,
            "price_vnd": r.price_vnd,
            "price_m": r.price_vnd / 1e6,
            "list_price_vnd": r.list_price_vnd,
            "discount_pct": r.discount_pct,
            "warranty_months": r.warranty_months,
            "return_days": r.return_days,
            "condition": r.condition,
            "availability": r.availability,
            "snapshot_date": r.snapshot_date,
            "quality_status": r.quality_status,
            "anomaly_flag": r.anomaly_flag,
            "fair_price": r.fair_price,
            "price_adv": r.price_adv,
            "shop_trust": r.shop_trust,
            "source_url": r.source_url,
            "release_year": r.release_year,
            "cpu": r.cpu,
            "cpu_benchmark_score": r.cpu_benchmark_score,
            "gpu": r.gpu,
            "gpu_benchmark_score": r.gpu_benchmark_score,
            "dgpu": r.dgpu,
            "ram_gb": r.ram_gb,
            "ssd_gb": r.ssd_gb,
            "screen_inch": r.screen_inch,
            "resolution_width_px": r.resolution_width_px,
            "resolution_height_px": r.resolution_height_px,
            "refresh_hz": r.refresh_hz,
            "weight_kg": r.weight_kg,
            "battery_wh": r.battery_wh
        } for r in records]

        return pd.DataFrame(data)

    def evaluate(self, persona: Dict[str, Any], df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Chấm điểm toàn diện cho tập offer theo hồ sơ người mua (Persona).
        Tái hiện 100% logic hàm dss(P) trong ASM2.
        """
        if df is None:
            df = self.get_offers_dataframe(snapshot_date="2026-10-08")
        
        c = df.copy()
        if len(c) == 0:
            return c

        # 1. Tính Utility: tổng có trọng số w_k * S_k
        utility = np.zeros(len(c), dtype=float)
        for k, wk in persona.get("w", {}).items():
            if k not in CRITERIA_MAP:
                continue
            col, kind, _ = CRITERIA_MAP[k]
            rk = persona.get("r", {}).get(k, 0.0)
            c["S_" + k] = S_k(c[col].values, rk, kind, XMAX[k], XMIN[k])
            utility += wk * c["S_" + k].values

        c["utility"] = utility

        # 2. Tính Deal: Sigmoid(kz * z) * Shop_Trust với z = ln(fair_price / price_vnd) / sigma
        SIGMA_LOG = 0.166307
        kz = float(persona.get("kz", 1.5))
        if "kz" not in persona and float(persona.get("k", 1.5)) == 10.0:
            kz = 1.5

        if "z" not in c.columns or c["z"].isnull().all():
            z_scores = np.log(c["fair_price"].values / c["price_vnd"].values) / SIGMA_LOG
            c["z"] = z_scores

        c["deal"] = sigmoid(kz * c["z"].values) * c["shop_trust"].values

        # 3. Tính Eligibility
        budget = float(persona.get("budget", 30_000_000))
        el = (c["price_vnd"] <= budget) & (c["quality_status"] == "pass")
        
        for hard_rule in persona.get("hard", []):
            col, op, val = hard_rule
            # Ánh xạ tên cột tương đương nếu cần
            if col not in c.columns and col == "cpu_benchmark_score" and "cpu_benchmark" in c.columns:
                col = "cpu_benchmark"
            elif col not in c.columns and col == "cpu_benchmark" and "cpu_benchmark_score" in c.columns:
                col = "cpu_benchmark_score"

            if col in c.columns:
                if op == ">=":
                    el &= (c[col] >= val)
                elif op == "<=":
                    el &= (c[col] <= val)
                elif op == "==" or op == "=":
                    el &= (c[col] == val)
                elif op == "!=":
                    el &= (c[col] != val)

        c["eligible"] = el.astype(int)

        # 4. Điểm tổng hợp DSS_Score
        alpha = float(persona.get("alpha", 0.65))
        c["dss_score"] = c["eligible"] * (alpha * c["utility"] + (1.0 - alpha) * c["deal"])

        # 5. Sắp xếp thứ hạng (rank)
        c = c.sort_values(by=["dss_score", "utility"], ascending=[False, False]).reset_index(drop=True)
        c["rank"] = np.where(c["eligible"] == 1, np.arange(1, len(c) + 1), np.nan)

        return c
