"""
offers.py - GET /api/offers endpoint (phân trang, lọc theo hãng/giá/RAM/nhà bán/tình trạng)
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from laptopmatch_dss.data_subsystem.db import get_db
from laptopmatch_dss.data_subsystem.models import Offer, Laptop, Seller

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Offers Catalog"])

@router.get("/offers", summary="Tra cứu danh sách Offer (phân trang, lọc, sắp xếp)")
def list_offers(
    skip: int = Query(0, ge=0, description="Vị trí bắt đầu"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng kết quả mỗi trang"),
    brand: Optional[str] = Query(None, description="Lọc theo thương hiệu (ASUS, Lenovo, HP, Apple...)"),
    seller_id: Optional[str] = Query(None, description="Lọc theo nhà bán (FPT, CPS, GEARVN, SAZO, TTCENTER, NCPC)"),
    min_price: Optional[float] = Query(None, description="Giá bán tối thiểu (VND)"),
    max_price: Optional[float] = Query(None, description="Giá bán tối đa (VND)"),
    ram_gb: Optional[int] = Query(None, description="RAM tối thiểu (GB)"),
    condition: Optional[str] = Query(None, description="Tình trạng máy (new, likenew, display)"),
    availability: Optional[str] = Query(None, description="Trạng thái hàng (in_stock, pre_order, out_of_stock)"),
    sort_by: Optional[str] = Query("price_asc", description="Sắp xếp: price_asc, price_desc, discount_desc, model_asc"),
    db: Session = Depends(get_db)
):
    """
    Truy vấn kho 210 offers với bộ lọc đa chiều và phân trang.
    """
    query = db.query(Offer).join(Laptop, Offer.laptop_id == Laptop.laptop_id).join(Seller, Offer.seller_id == Seller.seller_id)

    if brand:
        query = query.filter(Laptop.brand.ilike(f"%{brand}%"))
    if seller_id:
        query = query.filter(Offer.seller_id == seller_id)
    if min_price is not None:
        query = query.filter(Offer.price_vnd >= min_price)
    if max_price is not None:
        query = query.filter(Offer.price_vnd <= max_price)
    if ram_gb is not None:
        query = query.filter(Laptop.ram_gb >= ram_gb)
    if condition:
        query = query.filter(Offer.condition == condition)
    if availability:
        query = query.filter(Offer.availability == availability)

    total_count = query.count()

    if sort_by == "price_desc":
        query = query.order_by(desc(Offer.price_vnd))
    elif sort_by == "discount_desc":
        query = query.order_by(desc(Offer.discount_pct))
    elif sort_by == "model_asc":
        query = query.order_by(asc(Laptop.model))
    else: # price_asc
        query = query.order_by(asc(Offer.price_vnd))

    items = query.offset(skip).limit(limit).all()

    results = []
    for o in items:
        results.append({
            "offer_id": o.offer_id,
            "laptop_id": o.laptop_id,
            "brand": o.laptop.brand,
            "model": o.laptop.model,
            "seller_id": o.seller_id,
            "seller_name": o.seller.seller_name,
            "city": o.seller.city,
            "price_vnd": o.price_vnd,
            "list_price_vnd": o.list_price_vnd,
            "discount_pct": o.discount_pct,
            "warranty_months": o.warranty_months,
            "condition": o.condition,
            "availability": o.availability,
            "source_url": o.source_url,
            "specs": {
                "cpu": o.laptop.cpu,
                "cpu_benchmark": o.laptop.cpu_benchmark_score,
                "ram_gb": o.laptop.ram_gb,
                "ssd_gb": o.laptop.ssd_gb,
                "gpu": o.laptop.gpu,
                "dgpu": o.laptop.dgpu,
                "weight_kg": o.laptop.weight_kg,
                "battery_wh": o.laptop.battery_wh,
                "screen_inch": o.laptop.screen_inch,
                "resolution": f"{o.laptop.resolution_width_px}x{o.laptop.resolution_height_px}"
            }
        })

    return {
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "offers": results
    }
