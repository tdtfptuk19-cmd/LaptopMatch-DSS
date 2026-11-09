"""
models.py - Định nghĩa Lược đồ ORM (SQLAlchemy) cho LaptopMatch DSS
Bao gồm:
- dim_laptops: Thông số kỹ thuật của từng mẫu máy
- dim_sellers: Thông tin các nhà bán lẻ
- fact_offers: Các chào bán (offer) theo thời điểm snapshot (hỗ trợ T1, T2, T3)
- fact_telemetry_events & fact_user_feedback: Theo dõi hành vi và đo lường RAR
"""
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, Float, String, Boolean, DateTime, Date, ForeignKey, Text, Index
)
from sqlalchemy.orm import relationship
from laptopmatch_dss.data_subsystem.db import Base

class Laptop(Base):
    __tablename__ = "dim_laptops"

    laptop_id = Column(String(50), primary_key=True, index=True)
    brand = Column(String(50), nullable=False, index=True)
    model = Column(String(150), nullable=False, index=True)
    release_year = Column(Integer, nullable=False)
    
    # Cấu hình phần cứng
    cpu = Column(String(100), nullable=False)
    cpu_benchmark_score = Column(Integer, nullable=False)
    gpu = Column(String(100), nullable=False)
    gpu_benchmark_score = Column(Integer, nullable=False)
    dgpu = Column(Integer, default=0, nullable=False) # 1: card rời RTX, 0: iGPU
    ram_gb = Column(Integer, nullable=False, index=True)
    ssd_gb = Column(Integer, nullable=False, index=True)
    screen_inch = Column(Float, nullable=False)
    resolution_width_px = Column(Integer, nullable=False)
    resolution_height_px = Column(Integer, nullable=False)
    refresh_hz = Column(Integer, default=60, nullable=False)
    weight_kg = Column(Float, nullable=False, index=True)
    battery_wh = Column(Float, nullable=False)

    # Quan hệ
    offers = relationship("Offer", back_populates="laptop", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Laptop {self.laptop_id}: {self.brand} {self.model}>"


class Seller(Base):
    __tablename__ = "dim_sellers"

    seller_id = Column(String(50), primary_key=True, index=True)
    seller_name = Column(String(100), nullable=False, unique=True)
    seller_rating = Column(Float, default=4.5)
    seller_location = Column(String(200), nullable=False)
    city = Column(String(50), nullable=False, index=True)
    source_id = Column(String(50), nullable=True)

    # Quan hệ
    offers = relationship("Offer", back_populates="seller", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Seller {self.seller_id}: {self.seller_name}>"


class Offer(Base):
    __tablename__ = "fact_offers"

    offer_id = Column(String(50), primary_key=True, index=True) # e.g. OBS0001
    laptop_id = Column(String(50), ForeignKey("dim_laptops.laptop_id"), nullable=False, index=True)
    seller_id = Column(String(50), ForeignKey("dim_sellers.seller_id"), nullable=False, index=True)
    
    # Giá và khuyến mãi
    price_vnd = Column(Float, nullable=False, index=True)
    list_price_vnd = Column(Float, nullable=True)
    discount_pct = Column(Float, default=0.0)
    
    # Chính sách dịch vụ
    warranty_months = Column(Integer, default=12, nullable=False)
    return_days = Column(Integer, default=7, nullable=False)
    promo_flag = Column(Boolean, default=False)
    
    # Bổ sung 2 trường theo quan sát O8
    condition = Column(String(50), default="new", nullable=False) # 'new', 'likenew', 'display'
    availability = Column(String(50), default="in_stock", nullable=False) # 'in_stock', 'out_of_stock', 'pre_order'
    
    # Thời gian snapshot (R6: phục vụ ghi nhận T1, T2, T3)
    snapshot_date = Column(Date, default=date.today, nullable=False, index=True)
    source_url = Column(Text, nullable=True)
    
    # Dữ liệu chất lượng & định giá Hedonic
    core_completeness_pct = Column(Float, default=100.0)
    quality_status = Column(String(50), default="pass", index=True) # 'pass', 'needs_verification'
    anomaly_flag = Column(String(100), nullable=True) # e.g. 'very_high_price_verify'
    
    # Kết quả phân tích (có thể tính trước hoặc lưu trữ)
    fair_price = Column(Float, nullable=True)
    price_adv = Column(Float, nullable=True)
    shop_trust = Column(Float, nullable=True)

    # Quan hệ
    laptop = relationship("Laptop", back_populates="offers")
    seller = relationship("Seller", back_populates="offers")

    __table_args__ = (
        Index("idx_offer_lookup", "laptop_id", "seller_id", "snapshot_date"),
    )

    def __repr__(self):
        return f"<Offer {self.offer_id}: {self.laptop_id} @ {self.seller_id} - {self.price_vnd:,.0f} VND ({self.snapshot_date})>"


class TelemetryEvent(Base):
    __tablename__ = "fact_telemetry_events"

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False, index=True) # 'view_seller', 'save_laptop', 'copy_config', 'pin_compare'
    offer_id = Column(String(50), ForeignKey("fact_offers.offer_id"), nullable=True)
    persona = Column(String(20), nullable=True, index=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class UserFeedback(Base):
    __tablename__ = "fact_user_feedback"

    feedback_id = Column(Integer, primary_key=True, autoincrement=True)
    offer_id = Column(String(50), ForeignKey("fact_offers.offer_id"), nullable=True)
    persona = Column(String(20), nullable=True)
    is_helpful = Column(Boolean, nullable=False) # Nút Có/Không
    rating = Column(Integer, nullable=True) # Thang 1-5
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
