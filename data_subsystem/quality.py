"""
quality.py - Báo cáo & Kiểm định chất lượng dữ liệu (Data Quality Subsystem)
Thực hiện kiểm tra missing values, duplicates, outliers (OBS0075), và độ toàn vẹn sau nạp.
"""
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np

from laptopmatch_dss.data_subsystem.db import SessionLocal
from laptopmatch_dss.data_subsystem.models import Laptop, Seller, Offer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class DataQualityAuditor:
    def __init__(self, db: Session = None):
        self.db = db if db else SessionLocal()
        self._owns_db = db is None

    def close(self):
        if self._owns_db and self.db:
            self.db.close()

    def audit_all(self, snapshot_date = None) -> Dict[str, Any]:
        """
        Chạy toàn diện bộ kiểm tra chất lượng dữ liệu:
        - Kiểm tra số lượng bản ghi
        - Kiểm tra giá trị rỗng (missing values)
        - Kiểm tra tính trùng lặp (duplicates)
        - Phát hiện ngoại lai (outliers - ví dụ OBS0075)
        - Thống kê tỷ lệ pass/needs_verification
        """
        # Load dữ liệu vào DataFrame để phân tích vector hóa
        query = self.db.query(
            Offer.offer_id,
            Offer.laptop_id,
            Offer.seller_id,
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
            Offer.core_completeness_pct,
            Laptop.brand,
            Laptop.model,
            Laptop.cpu_benchmark_score,
            Laptop.gpu_benchmark_score,
            Laptop.ram_gb,
            Laptop.ssd_gb,
            Laptop.weight_kg,
            Laptop.battery_wh,
            Seller.seller_name,
            Seller.city
        ).join(Laptop, Offer.laptop_id == Laptop.laptop_id)\
         .join(Seller, Offer.seller_id == Seller.seller_id)

        if snapshot_date:
            query = query.filter(Offer.snapshot_date == snapshot_date)

        records = query.all()
        df = pd.DataFrame([{
            "offer_id": r.offer_id,
            "laptop_id": r.laptop_id,
            "seller_id": r.seller_id,
            "seller_name": r.seller_name,
            "price_vnd": r.price_vnd,
            "list_price_vnd": r.list_price_vnd,
            "discount_pct": r.discount_pct,
            "warranty_months": r.warranty_months,
            "return_days": r.return_days,
            "condition": r.condition,
            "availability": r.availability,
            "snapshot_date": r.snapshot_date,
            "quality_status": r.quality_status,
            "anomaly_flag": r.anomaly_flag,
            "core_completeness_pct": r.core_completeness_pct,
            "brand": r.brand,
            "model": r.model,
            "cpu_score": r.cpu_benchmark_score,
            "gpu_score": r.gpu_benchmark_score,
            "ram_gb": r.ram_gb,
            "ssd_gb": r.ssd_gb,
            "weight_kg": r.weight_kg,
            "battery_wh": r.battery_wh,
            "city": r.city
        } for r in records])

        total_records = len(df)
        if total_records == 0:
            return {"status": "empty", "total_records": 0, "message": "Không có bản ghi nào để kiểm tra."}

        # 1. Kiểm tra Missing Values
        missing_counts = df.isnull().sum()
        critical_cols = ["offer_id", "laptop_id", "seller_id", "price_vnd", "cpu_score", "ram_gb", "ssd_gb", "weight_kg"]
        critical_missing = {col: int(missing_counts[col]) for col in critical_cols if missing_counts[col] > 0}

        # 2. Kiểm tra Duplicate Offer ID
        dup_offer_ids = df[df.duplicated(subset=["offer_id"], keep=False)]["offer_id"].tolist()

        # 3. Phát hiện Outlier
        # Outlier giá (> 100tr hoặc IQR)
        high_price_threshold = 100_000_000 # 100 triệu VND
        price_outliers = df[df["price_vnd"] >= high_price_threshold][["offer_id", "brand", "model", "seller_id", "price_vnd"]].to_dict(orient="records")

        # Outlier cân nặng (< 0.8kg hoặc > 3.5kg)
        weight_outliers = df[(df["weight_kg"] < 0.8) | (df["weight_kg"] > 3.5)][["offer_id", "brand", "model", "weight_kg"]].to_dict(orient="records")

        # 4. Thống kê Quality Status
        quality_counts = df["quality_status"].value_counts().to_dict()
        flagged_anomalies = df[df["anomaly_flag"].notna()][["offer_id", "brand", "model", "anomaly_flag"]].to_dict(orient="records")

        # 5. Độ toàn vẹn dữ liệu lõi
        avg_completeness = float(df["core_completeness_pct"].mean())
        below_100_completeness = df[df["core_completeness_pct"] < 100.0][["offer_id", "brand", "model", "core_completeness_pct"]].to_dict(orient="records")

        report = {
            "status": "pass" if len(critical_missing) == 0 and len(dup_offer_ids) == 0 else "failed",
            "total_records": total_records,
            "critical_missing_fields": critical_missing,
            "duplicate_offer_ids": dup_offer_ids,
            "price_outliers_count": len(price_outliers),
            "price_outliers": price_outliers,
            "weight_outliers_count": len(weight_outliers),
            "weight_outliers": weight_outliers,
            "quality_status_breakdown": quality_counts,
            "anomaly_flagged_count": len(flagged_anomalies),
            "anomaly_flagged": flagged_anomalies,
            "average_core_completeness_pct": round(avg_completeness, 2),
            "below_100_completeness_count": len(below_100_completeness),
            "below_100_completeness": below_100_completeness
        }

        return report

def generate_quality_report() -> Dict[str, Any]:
    auditor = DataQualityAuditor()
    try:
        report = auditor.audit_all()
        logger.info("=" * 60)
        logger.info("BÁO CÁO CHẤT LƯỢNG DỮ LIỆU:")
        logger.info(f"Tổng số bản ghi: {report['total_records']}")
        logger.info(f"Missing fields nguy cấp: {report['critical_missing_fields']}")
        logger.info(f"Trùng lặp offer_id: {len(report['duplicate_offer_ids'])}")
        logger.info(f"Ngoại lai giá (>= 100tr): {report['price_outliers_count']} (Chi tiết: {report['price_outliers']})")
        logger.info(f"Phân loại chất lượng: {report['quality_status_breakdown']}")
        logger.info(f"Độ hoàn thiện lõi TB: {report['average_core_completeness_pct']}%")
        logger.info("=" * 60)
        return report
    finally:
        auditor.close()

if __name__ == "__main__":
    rep = generate_quality_report()
