"""
test_data_subsystem.py - Unit tests cho Data Management Subsystem (Giai đoạn 1)
Kiểm thử toàn diện:
1. Khởi tạo schema cơ sở dữ liệu
2. Tính toàn vẹn và tính Idempotent của migration từ Excel
3. Tính bảo toàn dữ liệu snapshot T1 (210 offer)
4. Bộ kiểm toán chất lượng dữ liệu (Data Quality Audit, phát hiện ngoại lai OBS0075)
5. Hoạt động của các Scraper Adapter và khả năng nạp snapshot mới (T2)
"""
import pytest
from datetime import date
from sqlalchemy import inspect

from laptopmatch_dss.data_subsystem.db import engine, SessionLocal, init_db
from laptopmatch_dss.data_subsystem.models import Laptop, Seller, Offer
from laptopmatch_dss.data_subsystem.migrate import migrate_data, calculate_hedonic_fair_price, calculate_shop_trust
from laptopmatch_dss.data_subsystem.quality import DataQualityAuditor
from laptopmatch_dss.data_subsystem.scrapers.scraper_runner import ScraperRunner
from laptopmatch_dss.data_subsystem.scrapers.fpt_scraper import FPTShopScraper
from laptopmatch_dss.data_subsystem.scrapers.sazo_scraper import SazoScraper

@pytest.fixture(scope="module")
def db_session():
    init_db()
    session = SessionLocal()
    yield session
    session.close()

def test_database_schema_creation(db_session):
    """Kiểm tra sự tồn tại của tất cả các bảng trong lược đồ."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    expected_tables = [
        "dim_laptops",
        "dim_sellers",
        "fact_offers",
        "fact_telemetry_events",
        "fact_user_feedback"
    ]
    for table in expected_tables:
        assert table in tables, f"Thiếu bảng trong CSDL: {table}"

def test_migration_and_idempotency(db_session):
    """Kiểm tra ETL nạp đúng 6 nhà bán, 210 offer T1 và có tính idempotent."""
    # Chạy lần 1
    res1 = migrate_data(db=db_session)
    assert res1["status"] == "success"
    assert res1["sellers"] == 6
    assert res1["t1_offers"] == 210

    # Chạy lần 2 (kiểm tra tính idempotent)
    res2 = migrate_data(db=db_session)
    assert res2["status"] == "success"
    assert res2["sellers"] == 6
    assert res2["t1_offers"] == 210

    # Kiểm tra danh sách 6 nhà bán chính xác
    sellers = {s.seller_id: s.seller_name for s in db_session.query(Seller).all()}
    expected_sellers = ["FPT", "CPS", "GEAR", "SAZO", "T&T Center", "NCPC"]
    for sid in expected_sellers:
        assert sid in sellers, f"Thiếu nhà bán: {sid}"

def test_foreign_key_and_data_fields_integrity(db_session):
    """Kiểm tra ràng buộc khóa ngoại và 2 trường bổ sung condition, availability (O8)."""
    t1_date = date(2026, 10, 8)
    offers = db_session.query(Offer).filter(Offer.snapshot_date == t1_date).all()
    assert len(offers) == 210

    for offer in offers:
        assert offer.laptop is not None, f"Offer {offer.offer_id} không liên kết với laptop"
        assert offer.seller is not None, f"Offer {offer.offer_id} không liên kết với seller"
        assert offer.condition in ["new", "likenew", "display"], f"Sai condition: {offer.condition}"
        assert offer.availability in ["in_stock", "out_of_stock", "pre_order"], f"Sai availability: {offer.availability}"
        assert offer.price_vnd > 0, f"Giá không hợp lệ: {offer.price_vnd}"

def test_ground_truth_top1_fair_price(db_session):
    """Kiểm tra offer OBS0164 (Top-1 Q1) khớp chính xác số liệu ASM2 v7."""
    top1 = db_session.query(Offer).filter(Offer.offer_id == "OBS0164").first()
    assert top1 is not None, "Không tìm thấy OBS0164 trong CSDL"
    
    assert top1.seller_id == "SAZO"
    assert top1.price_vnd == 24_500_000
    
    # Fair Price phải xấp xỉ 31.84tr VND (sai số < 0.01%)
    expected_fp = 31841187.40
    assert abs(top1.fair_price - expected_fp) / expected_fp < 0.001
    
    # Price advantage xấp xỉ +23.06%
    expected_adv = 23.0556
    assert abs(top1.price_adv - expected_adv) < 0.01

def test_data_quality_auditor(db_session):
    """Kiểm tra module audit phát hiện đầy đủ outlier OBS0075 và báo cáo đúng."""
    auditor = DataQualityAuditor(db=db_session)
    report = auditor.audit_all()
    
    assert report["status"] == "pass"
    assert report["total_records"] >= 210
    assert len(report["critical_missing_fields"]) == 0
    assert len(report["duplicate_offer_ids"]) == 0
    
    # OBS0075 là ngoại lai giá 179.99 triệu
    outlier_ids = [o["offer_id"] for o in report["price_outliers"]]
    assert "OBS0075" in outlier_ids
    assert report["average_core_completeness_pct"] >= 99.9

def test_scraper_adapters_mock():
    """Kiểm tra các adapter scraper hoạt động độc lập ở chế độ mock."""
    fpt = FPTShopScraper()
    fpt_offers = fpt.scrape(use_mock=True)
    assert len(fpt_offers) >= 1
    assert all(o["seller_id"] == "FPT" for o in fpt_offers)

    sazo = SazoScraper()
    sazo_offers = sazo.scrape(use_mock=True)
    assert len(sazo_offers) >= 1
    assert all(o["seller_id"] == "SAZO" for o in sazo_offers)

def test_scraper_runner_t2_ingestion_preserves_t1(db_session):
    """Kiểm tra runner nạp snapshot T2 mà TUYỆT ĐỐI không ghi đè snapshot T1 (R6)."""
    t1_date = date(2026, 10, 8)
    t2_date = date(2026, 11, 1)

    runner = ScraperRunner(db=db_session)
    res = runner.run_ingestion(snapshot_date=t2_date, use_mock=True)
    
    assert res["status"] == "success"
    assert res["t1_preserved_count"] == 210

    # Kiểm tra trực tiếp trên DB
    t1_count = db_session.query(Offer).filter(Offer.snapshot_date == t1_date).count()
    t2_count = db_session.query(Offer).filter(Offer.snapshot_date == t2_date).count()

    assert t1_count == 210, f"Snapshot T1 bị thay đổi: {t1_count} != 210"
    assert t2_count >= 6, f"Snapshot T2 không đủ offer: {t2_count}"
