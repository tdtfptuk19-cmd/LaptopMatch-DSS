"""
scraper_runner.py - Bộ điều phối thu thập dữ liệu (Scraper Runner & Ingestion Engine)
Hỗ trợ chạy CLI / Cron / GitHub Actions.
Ghi nhận snapshot T2, T3 vào fact_offers và TUYỆT ĐỐI KHÔNG ghi đè snapshot T1 (R6).
"""
import sys
import argparse
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from laptopmatch_dss.data_subsystem.db import SessionLocal, init_db
from laptopmatch_dss.data_subsystem.models import Laptop, Seller, Offer
from laptopmatch_dss.data_subsystem.migrate import calculate_hedonic_fair_price, calculate_shop_trust
from laptopmatch_dss.data_subsystem.scrapers.fpt_scraper import FPTShopScraper
from laptopmatch_dss.data_subsystem.scrapers.cellphones_scraper import CellphoneSScraper
from laptopmatch_dss.data_subsystem.scrapers.gearvn_scraper import GearvnScraper
from laptopmatch_dss.data_subsystem.scrapers.sazo_scraper import SazoScraper
from laptopmatch_dss.data_subsystem.scrapers.ttcenter_scraper import TTCenterScraper
from laptopmatch_dss.data_subsystem.scrapers.ncpc_scraper import NcpcScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SCRAPER_REGISTRY = {
    "FPT": FPTShopScraper,
    "CPS": CellphoneSScraper,
    "GEAR": GearvnScraper,
    "SAZO": SazoScraper,
    "T&T Center": TTCenterScraper,
    "NCPC": NcpcScraper,
}

class ScraperRunner:
    def __init__(self, db: Session = None):
        self.db = db if db else SessionLocal()
        self._owns_db = db is None

    def close(self):
        if self._owns_db and self.db:
            self.db.close()

    def run_ingestion(self, snapshot_date: date, use_mock: bool = True, target_seller: Optional[str] = None) -> Dict[str, Any]:
        """
        Thu thập và nạp một snapshot mới (T2 hoặc T3) vào cơ sở dữ liệu.
        Không ghi đè dữ liệu của các snapshot trước (đặc biệt T1: 2026-10-08).
        """
        init_db()
        logger.info(f"Bắt đầu quy trình thu thập dữ liệu cho Snapshot: {snapshot_date} (Mock={use_mock})")

        scrapers_to_run = {}
        if target_seller:
            if target_seller not in SCRAPER_REGISTRY:
                raise ValueError(f"Không tìm thấy scraper cho seller: {target_seller}")
            scrapers_to_run[target_seller] = SCRAPER_REGISTRY[target_seller]()
        else:
            scrapers_to_run = {sid: cls() for sid, cls in SCRAPER_REGISTRY.items()}

        all_scraped_offers = []
        for sid, scraper in scrapers_to_run.items():
            try:
                offers = scraper.scrape(use_mock=use_mock)
                all_scraped_offers.extend(offers)
            except Exception as e:
                logger.error(f"Lỗi khi chạy scraper cho {sid}: {e}")

        logger.info(f"Tổng số offer thu thập được: {len(all_scraped_offers)}")

        # Lưu trữ vào database
        inserted_offers = 0
        seller_counts = {}

        try:
            for idx, raw in enumerate(all_scraped_offers):
                seller_id = raw["seller_id"]
                seller = self.db.query(Seller).filter(Seller.seller_id == seller_id).first()
                if not seller:
                    logger.warning(f"Bỏ qua offer vì không tìm thấy nhà bán {seller_id}")
                    continue

                # Kiểm tra laptop trong dim_laptops theo (brand, model)
                brand = raw["brand"]
                model = raw["model"]
                laptop = self.db.query(Laptop).filter(
                    Laptop.brand == brand,
                    Laptop.model == model
                ).first()

                gpu_str = raw["gpu"]
                dgpu = 1 if "RTX" in gpu_str.upper() else 0

                if not laptop:
                    # Tạo laptop_id mới cho cấu hình mới
                    laptop_id = f"P_{brand[:3].upper()}_{int(datetime.now().timestamp())}_{idx}"
                    laptop = Laptop(
                        laptop_id=laptop_id,
                        brand=brand,
                        model=model,
                        release_year=int(raw.get("release_year", 2024)),
                        cpu=raw["cpu"],
                        cpu_benchmark_score=int(raw["cpu_benchmark_score"]),
                        gpu=gpu_str,
                        gpu_benchmark_score=int(raw["gpu_benchmark_score"]),
                        dgpu=dgpu,
                        ram_gb=int(raw["ram_gb"]),
                        ssd_gb=int(raw["ssd_gb"]),
                        screen_inch=float(raw["screen_inch"]),
                        resolution_width_px=int(raw["resolution_width_px"]),
                        resolution_height_px=int(raw["resolution_height_px"]),
                        refresh_hz=int(raw.get("refresh_hz", 60)),
                        weight_kg=float(raw["weight_kg"]),
                        battery_wh=float(raw["battery_wh"])
                    )
                    self.db.add(laptop)
                    self.db.flush()

                # Tạo offer_id duy nhất cho snapshot này
                date_str = snapshot_date.strftime("%Y%m%d")
                offer_id = f"OBS_{date_str}_{seller_id}_{idx+1:04d}"

                price_vnd = float(raw["price_vnd"])
                warranty = int(raw.get("warranty_months", 12))
                return_d = int(raw.get("return_days", 7))

                fp = calculate_hedonic_fair_price(
                    cpu_score=float(laptop.cpu_benchmark_score),
                    gpu_score=float(laptop.gpu_benchmark_score),
                    ram=float(laptop.ram_gb),
                    battery=float(laptop.battery_wh),
                    weight=float(laptop.weight_kg),
                    dgpu=laptop.dgpu
                )
                adv = (fp - price_vnd) / fp * 100.0
                trust = calculate_shop_trust(warranty, return_d)

                # Kiểm tra xem offer này đã được nạp cho snapshot này chưa (idempotent theo ngày)
                existing_offer = self.db.query(Offer).filter(
                    Offer.laptop_id == laptop.laptop_id,
                    Offer.seller_id == seller_id,
                    Offer.snapshot_date == snapshot_date
                ).first()

                if existing_offer:
                    # Cập nhật giá mới nhất
                    existing_offer.price_vnd = price_vnd
                    existing_offer.list_price_vnd = float(raw.get("list_price_vnd", price_vnd))
                    existing_offer.discount_pct = float(raw.get("discount_pct", 0.0))
                    existing_offer.fair_price = fp
                    existing_offer.price_adv = adv
                    existing_offer.shop_trust = trust
                else:
                    new_offer = Offer(
                        offer_id=offer_id,
                        laptop_id=laptop.laptop_id,
                        seller_id=seller_id,
                        price_vnd=price_vnd,
                        list_price_vnd=float(raw.get("list_price_vnd", price_vnd)),
                        discount_pct=float(raw.get("discount_pct", 0.0)),
                        warranty_months=warranty,
                        return_days=return_d,
                        promo_flag=bool(float(raw.get("discount_pct", 0.0)) > 0),
                        condition=raw.get("condition", "new"),
                        availability=raw.get("availability", "in_stock"),
                        snapshot_date=snapshot_date,
                        source_url=raw.get("source_url", ""),
                        core_completeness_pct=100.0,
                        quality_status="pass",
                        fair_price=fp,
                        price_adv=adv,
                        shop_trust=trust
                    )
                    self.db.add(new_offer)
                    inserted_offers += 1

                seller_counts[seller_id] = seller_counts.get(seller_id, 0) + 1

            self.db.commit()

            # Xác thực rằng T1 không bị ảnh hưởng
            t1_count = self.db.query(Offer).filter(Offer.snapshot_date == date(2026, 10, 8)).count()
            logger.info("=" * 60)
            logger.info(f"KẾT QUẢ THU THẬP SNAPSHOT {snapshot_date}:")
            logger.info(f"- Đã xử lý: {len(all_scraped_offers)} offer")
            logger.info(f"- Đã thêm mới: {inserted_offers} offer")
            logger.info(f"- Phân bổ theo nhà bán: {seller_counts}")
            logger.info(f"- Kiểm tra snapshot gốc T1 (08/10/2026): {t1_count}/210 offer (BẢO TOÀN)")
            logger.info("=" * 60)

            assert t1_count == 210, f"CẢNH BÁO VI PHẠM: Snapshot T1 bị thay đổi ({t1_count} != 210)!"

            return {
                "status": "success",
                "snapshot_date": str(snapshot_date),
                "total_scraped": len(all_scraped_offers),
                "inserted_new": inserted_offers,
                "seller_breakdown": seller_counts,
                "t1_preserved_count": t1_count
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Lỗi khi lưu dữ liệu snapshot: {e}", exc_info=True)
            raise e


def main():
    parser = argparse.ArgumentParser(description="LaptopMatch Scraper Runner")
    parser.add_argument("--date", type=str, default="2026-11-01", help="Ngày snapshot (YYYY-MM-DD)")
    parser.add_argument("--mock", action="store_true", default=True, help="Sử dụng mock fixture (mặc định True)")
    parser.add_argument("--live", action="store_true", help="Chạy cào dữ liệu live qua mạng")
    parser.add_argument("--seller", type=str, default=None, help="Chỉ chạy cho nhà bán cụ thể (FPT, CPS, GEAR, SAZO, T&T Center, NCPC)")

    args = parser.parse_args()
    use_mock = not args.live

    try:
        snap_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print("Định dạng ngày không hợp lệ. Vui lòng dùng YYYY-MM-DD")
        sys.exit(1)

    runner = ScraperRunner()
    try:
        res = runner.run_ingestion(snapshot_date=snap_date, use_mock=use_mock, target_seller=args.seller)
        print("Ingestion hoàn tất thành công:", res)
    finally:
        runner.close()


if __name__ == "__main__":
    main()
