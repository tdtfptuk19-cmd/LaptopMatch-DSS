"""
explainer.py - Smart Decision Explainer (Sinh lý giải tự nhiên tại sao máy Top-1 vượt trội)
Kèm chế độ Fallback template chuyên gia khi không có mạng hoặc hết quota.
"""
from typing import Dict, Any, List, Optional
from laptopmatch_dss.knowledge_subsystem.explanation import DecisionExplainer

class SmartExplainer(DecisionExplainer):
    """
    Kế thừa DecisionExplainer, mở rộng các phương thức sinh văn bản giải thích
    tự nhiên tại sao một offer vượt trội các đối thủ còn lại.
    """
    def generate_comparative_summary(self, top1_offer: Dict[str, Any], top2_offer: Dict[str, Any]) -> str:
        """So sánh trực diện Top 1 và Top 2."""
        top1_name = f"{top1_offer.get('brand')} {top1_offer.get('model')}"
        top2_name = f"{top2_offer.get('brand')} {top2_offer.get('model')}"
        dss_diff = (top1_offer.get("dss_score", 0.0) - top2_offer.get("dss_score", 0.0))
        price_diff_m = (top2_offer.get("price_vnd", 0.0) - top1_offer.get("price_vnd", 0.0)) / 1e6

        return (
            f"{top1_name} vượt trên {top2_name} với khoảng cách điểm DSS là +{dss_diff:.4f}. "
            f"Lợi thế cốt lõi đến từ mức chênh lệch giá tiết kiệm hơn {price_diff_m:+.2f} triệu VND "
            f"và trọng lượng tối ưu hơn ({top1_offer.get('weight_kg')}kg so với {top2_offer.get('weight_kg')}kg)."
        )

# Xuất bản phiên bản dùng chung
explainer = SmartExplainer()
