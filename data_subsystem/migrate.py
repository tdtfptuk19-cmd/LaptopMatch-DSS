"""
migrate.py - Script di chuyển dữ liệu (ETL) từ LaptopMatch_Clean.xlsx sang Database
Đảm bảo tính Idempotent (chạy nhiều lần không tạo bản ghi trùng lặp)
Tuân thủ đầy đủ ràng buộc khóa ngoại và bảo toàn dữ liệu T1 (2026-10-08).
"""
import sys
import logging
from datetime import datetime, date
from pathlib import Path

# Đảm bảo đường dẫn gốc cho phép import package laptopmatch_dss
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from laptopmatch_dss.config.settings import (
    ORIGINAL_DATASET_PATH,
    MODELS_CONFIG_PATH,
    BASE_DIR
)
from laptopmatch_dss.data_subsystem.db import engine, SessionLocal, init_db
from laptopmatch_dss.data_subsystem.models import Laptop, Seller, Offer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Bảng tra cứu thành phố theo nhà bán lẻ (từ phân tích ASM2/ASM3)
SELLER_CITIES = {
    "SAZO": "Hà Nội",
    "T&T Center": "TP. Đà Nẵng",
    "FPT": "TP. Hồ Chí Minh",
    "CPS": "TP. Hồ Chí Minh",
    "GEAR": "TP. Hồ Chí Minh",
    "NCPC": "Hà Nội",
}

def calculate_hedonic_fair_price(cpu_score: float, gpu_score: float, ram: float, 
                                 battery: float, weight: float, dgpu: int) -> float:
    """
    Tính Fair Price theo công thức Hedonic OLS Robust HC3 (ASM2):
    ln(Fair Price) = 16.514177 + 0.013954*(CPU/1000) + 0.016073*(GPU/1000) 
                     + 0.009088*RAM + 0.004434*Battery - 0.200707*Weight + 0.147567*RTX
    """
    ln_price = (
        16.514177
        + 0.013954 * (cpu_score / 1000.0)
        + 0.016073 * (gpu_score / 1000.0)
        + 0.009088 * ram
        + 0.004434 * battery
        - 0.200707 * weight
        + 0.147567 * dgpu
    )
    return float(np.exp(ln_price))


def calculate_shop_trust(warranty_months: int, return_days: int) -> float:
    """
    Tính Shop_Trust theo công thức ASM2:
    Shop_Trust = 0.90 + 0.05 * (warranty - 12)/12 + 0.05 * (return_days - 7)/23
    """
    trust = 0.90 + 0.05 * (warranty_months - 12) / 12.0 + 0.05 * (return_days - 7) / 23.0
    return float(trust)


def migrate_data(excel_path: Path = ORIGINAL_DATASET_PATH, db: Session = None):
    """
    Thực hiện ETL chuyển đổi dữ liệu từ Excel sang CSDL quan hệ.
    Chạy Idempotent: xóa và chèn lại T1 hoặc cập nhật nếu đã tồn tại.
    """
    if not excel_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file dữ liệu gốc: {excel_path}")

    # Đảm bảo bảng đã được tạo
    init_db()

    should_close_session = False
    if db is None:
        db = SessionLocal()
        should_close_session = True

    try:
        logger.info(f"Bắt đầu nạp dữ liệu từ: {excel_path}")
        
        # 1. Nạp dim_sellers
        df_sellers = pd.read_excel(excel_path, sheet_name="dim_seller")
        logger.info(f"Đọc {len(df_sellers)} nhà bán lẻ từ sheet dim_seller...")
        
        for _, row in df_sellers.iterrows():
            seller_id = str(row["seller_id"]).strip()
            city = SELLER_CITIES.get(seller_id)
            if not city:
                # Fallback từ seller_location
                loc = str(row["seller_location"])
                city = "Hà Nội" if "Hà Nội" in loc else ("TP. Đà Nẵng" if "Đà Nẵng" in loc else "TP. Hồ Chí Minh")
                
            existing_seller = db.query(Seller).filter(Seller.seller_id == seller_id).first()
            if existing_seller:
                existing_seller.seller_name = str(row["seller_name"]).strip()
                existing_seller.seller_rating = float(row.get("seller_rating", 4.5))
                existing_seller.seller_location = str(row["seller_location"]).strip()
                existing_seller.city = city
                existing_seller.source_id = str(row.get("source_id", "")).strip()
            else:
                new_seller = Seller(
                    seller_id=seller_id,
                    seller_name=str(row["seller_name"]).strip(),
                    seller_rating=float(row.get("seller_rating", 4.5)),
                    seller_location=str(row["seller_location"]).strip(),
                    city=city,
                    source_id=str(row.get("source_id", "")).strip()
                )
                db.add(new_seller)
        db.flush()
        logger.info("Hoàn tất nạp dim_sellers.")

        # 2. Nạp laptop_master (dim_laptops & fact_offers T1)
        df_master = pd.read_excel(excel_path, sheet_name="laptop_master")
        logger.info(f"Đọc {len(df_master)} dòng từ sheet laptop_master...")

        t1_date = date(2026, 10, 8)

        # Tải Fair Price và Price Advantage Out-of-Fold từ data/scored_offers.csv (ASM2 v7)
        oof_lookup = {}
        for candidate_path in [
            BASE_DIR.parent / "data" / "scored_offers.csv",
            Path("data/scored_offers.csv"),
            Path(__file__).resolve().parent.parent.parent / "data" / "scored_offers.csv"
        ]:
            if candidate_path.exists():
                try:
                    df_sc = pd.read_csv(candidate_path)
                    for _, r_sc in df_sc.iterrows():
                        oid = str(r_sc.get("observation_id", r_sc.get("offer_id", ""))).strip()
                        oof_lookup[oid] = {
                            "fair_price": float(r_sc["fair_price"]),
                            "price_adv": float(r_sc["price_adv"]),
                            "shop_trust": float(r_sc["shop_trust"]) if "shop_trust" in r_sc and pd.notna(r_sc["shop_trust"]) else None
                        }
                    logger.info(f"Đã nạp {len(oof_lookup)} out-of-fold Fair Price từ: {candidate_path}")
                    break
                except Exception as ex:
                    logger.warning(f"Lỗi đọc {candidate_path}: {ex}")

        for _, row in df_master.iterrows():
            obs_id = str(row["observation_id"]).strip()
            laptop_id = str(row["product_id"]).strip()
            seller_id = str(row["seller_id"]).strip()
            
            gpu_str = str(row["gpu"])
            dgpu = 1 if "RTX" in gpu_str.upper() else 0

            # Xử lý Laptop (dim_laptops)
            existing_laptop = db.query(Laptop).filter(Laptop.laptop_id == laptop_id).first()
            if existing_laptop:
                existing_laptop.brand = str(row["brand"]).strip()
                existing_laptop.model = str(row["model"]).strip()
                existing_laptop.release_year = int(row["release_year"])
                existing_laptop.cpu = str(row["cpu"]).strip()
                existing_laptop.cpu_benchmark_score = int(row["cpu_benchmark_score"])
                existing_laptop.gpu = gpu_str.strip()
                existing_laptop.gpu_benchmark_score = int(row["gpu_benchmark_score"])
                existing_laptop.dgpu = dgpu
                existing_laptop.ram_gb = int(row["ram_gb"])
                existing_laptop.ssd_gb = int(row["ssd_gb"])
                existing_laptop.screen_inch = float(row["screen_inch"])
                existing_laptop.resolution_width_px = int(row["resolution_width_px"])
                existing_laptop.resolution_height_px = int(row["resolution_height_px"])
                existing_laptop.refresh_hz = int(row.get("refresh_hz", 60))
                existing_laptop.weight_kg = float(row["weight_kg"])
                existing_laptop.battery_wh = float(row["battery_wh"])
            else:
                new_laptop = Laptop(
                    laptop_id=laptop_id,
                    brand=str(row["brand"]).strip(),
                    model=str(row["model"]).strip(),
                    release_year=int(row["release_year"]),
                    cpu=str(row["cpu"]).strip(),
                    cpu_benchmark_score=int(row["cpu_benchmark_score"]),
                    gpu=gpu_str.strip(),
                    gpu_benchmark_score=int(row["gpu_benchmark_score"]),
                    dgpu=dgpu,
                    ram_gb=int(row["ram_gb"]),
                    ssd_gb=int(row["ssd_gb"]),
                    screen_inch=float(row["screen_inch"]),
                    resolution_width_px=int(row["resolution_width_px"]),
                    resolution_height_px=int(row["resolution_height_px"]),
                    refresh_hz=int(row.get("refresh_hz", 60)),
                    weight_kg=float(row["weight_kg"]),
                    battery_wh=float(row["battery_wh"])
                )
                db.add(new_laptop)

            # Chuẩn hóa condition & availability (theo O8)
            raw_condition = str(row.get("condition", "Mới 100%")).lower()
            if "likenew" in raw_condition or "cũ" in raw_condition:
                condition_norm = "likenew"
            elif "trưng bày" in raw_condition or "display" in raw_condition:
                condition_norm = "display"
            else:
                condition_norm = "new"

            raw_avail = str(row.get("availability", "listed")).lower()
            if "hết" in raw_avail or "out_of_stock" in raw_avail:
                avail_norm = "out_of_stock"
            elif "đặt trước" in raw_avail or "pre_order" in raw_avail:
                avail_norm = "pre_order"
            else:
                avail_norm = "in_stock"

            # Tính toán phân tích
            price_vnd = float(row["price_vnd"])
            warranty = int(row.get("warranty_months", 12))
            return_d = int(row.get("return_days", 7))
            
            # Sử dụng Fair Price Out-of-Fold (v7) nếu có, fallback về mô hình OLS in-sample
            if obs_id in oof_lookup:
                fp = oof_lookup[obs_id]["fair_price"]
                adv = oof_lookup[obs_id]["price_adv"]
                trust = oof_lookup[obs_id]["shop_trust"] if oof_lookup[obs_id]["shop_trust"] is not None else calculate_shop_trust(warranty, return_d)
            else:
                fp = calculate_hedonic_fair_price(
                    cpu_score=float(row["cpu_benchmark_score"]),
                    gpu_score=float(row["gpu_benchmark_score"]),
                    ram=float(row["ram_gb"]),
                    battery=float(row["battery_wh"]),
                    weight=float(row["weight_kg"]),
                    dgpu=dgpu
                )
                adv = (fp - price_vnd) / fp * 100.0
                trust = calculate_shop_trust(warranty, return_d)

            # Xử lý Offer (fact_offers)
            existing_offer = db.query(Offer).filter(Offer.offer_id == obs_id).first()
            if existing_offer:
                existing_offer.laptop_id = laptop_id
                existing_offer.seller_id = seller_id
                existing_offer.price_vnd = price_vnd
                existing_offer.list_price_vnd = float(row.get("list_price_vnd", price_vnd))
                existing_offer.discount_pct = float(row.get("discount_pct", 0.0))
                existing_offer.warranty_months = warranty
                existing_offer.return_days = return_d
                existing_offer.promo_flag = bool(existing_offer.discount_pct > 0)
                existing_offer.condition = condition_norm
                existing_offer.availability = avail_norm
                existing_offer.snapshot_date = t1_date
                existing_offer.source_url = str(row.get("source_url", ""))
                existing_offer.core_completeness_pct = float(row.get("core_completeness_pct", 100.0))
                existing_offer.quality_status = str(row.get("quality_status", "pass")).strip()
                existing_offer.anomaly_flag = str(row.get("anomaly_flag", "")).strip() if pd.notna(row.get("anomaly_flag")) else None
                existing_offer.fair_price = fp
                existing_offer.price_adv = adv
                existing_offer.shop_trust = trust
            else:
                new_offer = Offer(
                    offer_id=obs_id,
                    laptop_id=laptop_id,
                    seller_id=seller_id,
                    price_vnd=price_vnd,
                    list_price_vnd=float(row.get("list_price_vnd", price_vnd)),
                    discount_pct=float(row.get("discount_pct", 0.0)),
                    warranty_months=warranty,
                    return_days=return_d,
                    promo_flag=bool(float(row.get("discount_pct", 0.0)) > 0),
                    condition=condition_norm,
                    availability=avail_norm,
                    snapshot_date=t1_date,
                    source_url=str(row.get("source_url", "")),
                    core_completeness_pct=float(row.get("core_completeness_pct", 100.0)),
                    quality_status=str(row.get("quality_status", "pass")).strip(),
                    anomaly_flag=str(row.get("anomaly_flag", "")).strip() if pd.notna(row.get("anomaly_flag")) else None,
                    fair_price=fp,
                    price_adv=adv,
                    shop_trust=trust
                )
                db.add(new_offer)

        db.commit()
        
        # Kiểm tra toàn vẹn
        seller_count = db.query(Seller).count()
        laptop_count = db.query(Laptop).count()
        offer_count = db.query(Offer).count()
        t1_count = db.query(Offer).filter(Offer.snapshot_date == t1_date).count()

        logger.info("=" * 60)
        logger.info("KẾT QUẢ DI CHUYỂN DỮ LIỆU:")
        logger.info(f"- dim_sellers: {seller_count}/6 nhà bán")
        logger.info(f"- dim_laptops: {laptop_count}/210 mẫu máy")
        logger.info(f"- fact_offers: {offer_count}/210 offer (T1: {t1_count})")
        logger.info("=" * 60)

        assert seller_count == 6, f"Sai số lượng nhà bán: {seller_count} != 6"
        assert offer_count >= 210, f"Thiếu offer: {offer_count} < 210"
        assert t1_count == 210, f"Sai số offer snapshot T1: {t1_count} != 210"

        return {
            "status": "success",
            "sellers": seller_count,
            "laptops": laptop_count,
            "offers": offer_count,
            "t1_offers": t1_count
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Lỗi di chuyển dữ liệu: {e}", exc_info=True)
        raise e
    finally:
        if should_close_session:
            db.close()


if __name__ == "__main__":
    result = migrate_data()
    print("Migration hoàn tất:", result)
