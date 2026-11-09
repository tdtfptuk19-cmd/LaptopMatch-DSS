"""
pricing.py - Quản lý mô hình định giá Hedonic OLS Robust HC3 (Model Management Subsystem)
Chức năng:
- Tái huấn luyện mô hình Hedonic từ CSDL quan hệ
- Ước lượng 6 hệ số beta, R2, MAPE (5-fold Cross-Validation)
- Kiểm định phương sai sai số thay đổi Breusch-Pagan (biện minh cho HC3)
- Đưa ra cảnh báo nếu MAPE > 15%
- Quản lý phiên bản mô hình (Model Registry) lưu dưới dạng JSON
- Dự báo Fair Price cho mẫu máy mới
"""
import os
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.diagnostic import het_breuschpagan
from sklearn.model_selection import KFold
from sqlalchemy.orm import Session

from laptopmatch_dss.config.settings import BASE_DIR, MODELS_CONFIG_PATH
from laptopmatch_dss.data_subsystem.db import SessionLocal
from laptopmatch_dss.data_subsystem.models import Offer, Laptop

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REGISTRY_DIR = BASE_DIR / "models_registry"

class HedonicPricingModel:
    """
    Bộ quản lý và ước lượng mô hình Hedonic Price Model:
    ln(Price) = beta0 + beta1*CPU + beta2*GPU + beta3*RAM + beta4*Battery + beta5*Weight + beta6*dGPU
    """
    def __init__(self, registry_dir: Path = REGISTRY_DIR):
        self.registry_dir = registry_dir
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.coefficients: Dict[str, float] = {}
        self.intercept: float = 0.0
        self.r_squared: float = 0.0
        self.mape_5fold: float = 0.0
        self.breusch_pagan_pvalue: float = 0.0
        self.sample_size: int = 0
        self.version: str = "init"
        self.snapshot_date: str = ""

    def fit_from_db(self, snapshot_date: date = date(2026, 10, 8), exclude_outliers: Tuple[str, ...] = ("OBS0075",), db: Session = None) -> Dict[str, Any]:
        """
        Huấn luyện mô hình từ dữ liệu trong CSDL của một snapshot cụ thể.
        Loại trừ ngoại lai cực đoan (như OBS0075 - giá 179.99 triệu, p < 0.001) để đảm bảo mô hình đại diện.
        """
        owns_db = db is None
        session = db if db else SessionLocal()

        try:
            logger.info(f"Đang tải dữ liệu snapshot {snapshot_date} để huấn luyện Hedonic OLS Robust HC3...")
            query = session.query(
                Offer.offer_id,
                Offer.price_vnd,
                Laptop.cpu_benchmark_score,
                Laptop.gpu_benchmark_score,
                Laptop.ram_gb,
                Laptop.battery_wh,
                Laptop.weight_kg,
                Laptop.dgpu
            ).join(Laptop, Offer.laptop_id == Laptop.laptop_id)\
             .filter(Offer.snapshot_date == snapshot_date)

            if exclude_outliers:
                query = query.filter(~Offer.offer_id.in_(exclude_outliers))

            records = query.all()
            if len(records) < 20:
                raise ValueError(f"Không đủ dữ liệu huấn luyện: {len(records)} bản ghi.")

            df = pd.DataFrame([{
                "offer_id": r.offer_id,
                "price_vnd": r.price_vnd,
                "cpu_k": r.cpu_benchmark_score / 1000.0,
                "gpu_k": r.gpu_benchmark_score / 1000.0,
                "ram_gb": r.ram_gb,
                "battery_wh": r.battery_wh,
                "weight_kg": r.weight_kg,
                "dgpu": r.dgpu
            } for r in records])

            # Chuẩn bị ma trận đặc trưng
            feature_cols = ["cpu_k", "gpu_k", "ram_gb", "battery_wh", "weight_kg", "dgpu"]
            X = df[feature_cols].copy()
            X["const"] = 1.0
            y = np.log(df["price_vnd"])

            # 1. Huấn luyện OLS với Robust Standard Errors HC3
            ols_model = OLS(y, X).fit(cov_type="HC3")

            self.intercept = float(ols_model.params["const"])
            self.coefficients = {col: float(ols_model.params[col]) for col in feature_cols}
            self.r_squared = float(ols_model.rsquared)
            self.sample_size = len(df)

            # 2. Kiểm định Breusch-Pagan phát hiện phương sai sai số thay đổi
            bp_test = het_breuschpagan(ols_model.resid, X)
            self.breusch_pagan_pvalue = float(bp_test[1])

            # 3. 5-fold Cross-Validation đo MAPE trên thang đo giá VND
            kf = KFold(n_splits=5, shuffle=True, random_state=42)
            cv_mapes = []
            for train_idx, val_idx in kf.split(df):
                m_fold = OLS(y.iloc[train_idx], X.iloc[train_idx]).fit(cov_type="HC3")
                y_pred_val = np.exp(m_fold.predict(X.iloc[val_idx]))
                y_true_val = df["price_vnd"].iloc[val_idx]
                fold_mape = np.mean(np.abs(y_pred_val - y_true_val) / y_true_val) * 100.0
                cv_mapes.append(fold_mape)

            self.mape_5fold = float(np.mean(cv_mapes))
            self.snapshot_date = str(snapshot_date)
            self.version = f"hedonic_ols_hc3_{snapshot_date.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S')}"

            # 4. Kiểm tra ngưỡng chất lượng
            if self.mape_5fold > 15.0:
                logger.warning(f"CẢNH BÁO MÔ HÌNH: MAPE = {self.mape_5fold:.2f}% vượt ngưỡng mục tiêu 15.0%!")
            else:
                logger.info(f"Mô hình đạt chuẩn: MAPE = {self.mape_5fold:.2f}% <= 15.0%, R2 = {self.r_squared:.4f}")

            # 5. Lưu phiên bản vào Model Registry
            model_metadata = self.save_model_version()

            return model_metadata

        finally:
            if owns_db and session:
                session.close()

    def predict_fair_price(self, cpu_benchmark_score: float, gpu_benchmark_score: float,
                           ram_gb: float, battery_wh: float, weight_kg: float, dgpu: int) -> float:
        """
        Dự báo Fair Price (VND) cho một cấu hình máy.
        ln(FP) = const + beta1*cpu_k + beta2*gpu_k + beta3*ram + beta4*battery + beta5*weight + beta6*dgpu
        """
        if not self.coefficients:
            self.load_latest_or_fallback()

        ln_fp = (
            self.intercept
            + self.coefficients["cpu_k"] * (cpu_benchmark_score / 1000.0)
            + self.coefficients["gpu_k"] * (gpu_benchmark_score / 1000.0)
            + self.coefficients["ram_gb"] * ram_gb
            + self.coefficients["battery_wh"] * battery_wh
            + self.coefficients["weight_kg"] * weight_kg
            + self.coefficients["dgpu"] * dgpu
        )
        return float(np.exp(ln_fp))

    def save_model_version(self) -> Dict[str, Any]:
        """Lưu metadata mô hình vào tệp JSON trong model registry."""
        metadata = {
            "version": self.version,
            "created_at": datetime.now().isoformat(),
            "snapshot_date": self.snapshot_date,
            "sample_size": self.sample_size,
            "r_squared": round(self.r_squared, 4),
            "mape_5fold_pct": round(self.mape_5fold, 2),
            "breusch_pagan_pvalue": round(self.breusch_pagan_pvalue, 5),
            "intercept": self.intercept,
            "coefficients": self.coefficients,
            "features": list(self.coefficients.keys()),
            "cov_type": "HC3"
        }
        file_path = self.registry_dir / f"{self.version}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Tạo symbolic/latest file
        latest_path = self.registry_dir / "latest_hedonic_model.json"
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"Đã lưu mô hình vào: {file_path}")
        return metadata

    def load_latest_or_fallback(self):
        """Tải mô hình mới nhất từ registry hoặc đọc từ models_config.json mặc định."""
        latest_path = self.registry_dir / "latest_hedonic_model.json"
        if latest_path.exists():
            with open(latest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.version = data.get("version", "loaded")
            self.intercept = data["intercept"]
            self.coefficients = data["coefficients"]
            self.r_squared = data.get("r_squared", 0.83)
            self.mape_5fold = data.get("mape_5fold_pct", 12.6)
            self.breusch_pagan_pvalue = data.get("breusch_pagan_pvalue", 0.018)
            self.sample_size = data.get("sample_size", 209)
            logger.info(f"Đã nạp mô hình từ registry: {self.version}")
            return

        # Fallback từ models_config.json
        if MODELS_CONFIG_PATH.exists():
            with open(MODELS_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            hed = cfg.get("hedonic_model", {})
            self.intercept = hed["beta_0_intercept"]
            self.coefficients = {
                "cpu_k": hed["beta_cpu_k"],
                "gpu_k": hed["beta_gpu_k"],
                "ram_gb": hed["beta_ram_gb"],
                "battery_wh": hed["beta_battery_wh"],
                "weight_kg": hed["beta_weight_kg"],
                "dgpu": hed["beta_dgpu_rtx"]
            }
            self.r_squared = hed.get("r_squared", 0.83)
            self.mape_5fold = hed.get("mape_pct", 12.6)
            self.sample_size = hed.get("sample_size", 209)
            self.version = "default_asm2_config"
            logger.info("Đã nạp tham số mô hình mặc định từ models_config.json.")
            return

        raise RuntimeError("Không tìm thấy mô hình trong registry hoặc models_config.json")
