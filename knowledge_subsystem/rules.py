"""
rules.py - Động cơ suy diễn Luật chuyên gia (Knowledge-based Subsystem)
Cài đặt hệ chuyên gia dựa trên luật (Forward-chaining Rule Engine)
Hiện thực hóa 20 giả thuyết khoa học và 6 khuyến nghị thực tiễn từ ASM2/ASM3.
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class RuleActivation:
    def __init__(self, rule_id: str, rule_name: str, category: str, message: str, severity: str = "info"):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.category = category # 'pricing', 'recommendation', 'budget', 'warning'
        self.message = message
        self.severity = severity # 'info', 'success', 'warning', 'danger'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "category": self.category,
            "message": self.message,
            "severity": self.severity
        }


class ExpertRuleEngine:
    """
    Hệ chuyên gia suy diễn luật dựa trên bằng chứng dữ liệu (Data-driven Knowledge Base).
    """

    @staticmethod
    def evaluate_offer_rules(offer: Dict[str, Any], persona: Dict[str, Any], market_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Đánh giá các luật cho một offer cụ thể theo hồ sơ người dùng.
        """
        activations = []
        price_adv = float(offer.get("price_adv", offer.get("price_adv_pct", 0.0)))
        price_vnd = float(offer.get("price_vnd", 0.0))
        budget = float(persona.get("budget", 30_000_000))
        brand = str(offer.get("brand", "")).strip()
        weight = float(offer.get("weight_kg", 2.0))
        battery = float(offer.get("battery_wh", 50.0))
        warranty = int(offer.get("warranty_months", 12))
        return_days = int(offer.get("return_days", 7))
        dgpu = int(offer.get("dgpu", 0))

        # Luật R1: Không dùng % giảm giá (H5 bị bác bỏ, H15 chấp nhận)
        discount_pct = float(offer.get("discount_pct", 0.0))
        if discount_pct > 20.0 and price_adv < 0.0:
            activations.append(RuleActivation(
                rule_id="R1_DISCOUNT_ILLUSION",
                rule_name="Cảnh báo Ảo ảnh Giảm giá (H5)",
                category="warning",
                message=f"Máy này giảm giá sâu ({discount_pct:.1f}%) nhưng giá bán vẫn đắt hơn Fair Price ({abs(price_adv):.1f}%). Khuyến nghị không mua dựa trên % giảm.",
                severity="warning"
            ).to_dict())

        # Luật R2: Cảnh báo đắt >= 10% hoặc Khen thưởng Deal hời >= 10%
        if price_adv <= -10.0:
            activations.append(RuleActivation(
                rule_id="R2_EXPENSIVE_WARNING",
                rule_name="Cảnh báo Giá đắt (Khuyến nghị R2)",
                category="pricing",
                message=f"Giá bán hiện tại cao hơn giá trị thực tế {abs(price_adv):.1f}%. Cân nhắc tìm nhà bán khác hoặc đợi đợt khuyến mãi.",
                severity="danger"
            ).to_dict())
        elif price_adv >= 10.0:
            activations.append(RuleActivation(
                rule_id="R2_BARGAIN_DEAL",
                rule_name="Deal Hời Vượt trội (Khuyến nghị R2)",
                category="pricing",
                message=f"Mức giá rất hời! Thấp hơn giá trị thực tế {price_adv:.1f}%, tiết kiệm đáng kể ngân sách.",
                severity="success"
            ).to_dict())

        # Luật R3: Cùng mẫu nhiều nơi bán (Minh chứng H4: p < 0.001)
        if market_context and market_context.get("has_multiple_sellers"):
            cheapest_seller = market_context.get("cheapest_seller", "")
            price_diff = market_context.get("seller_price_diff_vnd", 0.0)
            if price_diff > 500_000:
                activations.append(RuleActivation(
                    rule_id="R3_CROSS_SELLER_ARBITRAGE",
                    rule_name="Chênh lệch Giá giữa các Nhà bán (H4 / R3)",
                    category="recommendation",
                    message=f"Mẫu máy này có mặt ở nhiều nơi; mua tại {cheapest_seller} tiết kiệm được {price_diff/1e6:.1f} triệu VND so với nơi đắt nhất.",
                    severity="info"
                ).to_dict())

        # Luật R4: Đánh đổi Hiệu năng vs Di động (H2, H14)
        if dgpu == 1 and weight > 2.0:
            activations.append(RuleActivation(
                rule_id="R4_GAMING_PORTABILITY_TRADEOFF",
                rule_name="Đánh đổi Di động và Gaming (H2/H14)",
                category="recommendation",
                message=f"Máy trang bị card đồ họa rời RTX nhưng nặng {weight:.2f}kg. Thích hợp để bàn hoặc gaming, hạn chế di chuyển thường xuyên.",
                severity="info"
            ).to_dict())
        elif dgpu == 0 and weight <= 1.3:
            activations.append(RuleActivation(
                rule_id="R4_ULTRAPORTABLE_FIT",
                rule_name="Tối ưu Di động Tuyệt vời (WS4 / H2)",
                category="recommendation",
                message=f"Trọng lượng siêu nhẹ {weight:.2f}kg kết hợp pin {battery:.0f}Wh, tối ưu tối đa cho sinh viên mang lên giảng đường hàng ngày.",
                severity="success"
            ).to_dict())

        # Luật R5: Ràng buộc tối thiểu cho Sinh viên Lập trình (WS1 / R5)
        if budget < 20_000_000 and int(offer.get("ram_gb", 0)) >= 16:
            activations.append(RuleActivation(
                rule_id="R5_MINIMUM_BUDGET_ADVICE",
                rule_name="Khuyến nghị Ngân sách Lập trình (R5)",
                category="budget",
                message="Dưới 20 triệu rất hiếm máy cấu hình RAM 16GB/SSD 512GB đạt chuẩn chất lượng cao. Khuyến nghị chuẩn bị ngân sách tối thiểu 20 triệu.",
                severity="warning"
            ).to_dict())

        # Luật R3b: Chính sách hậu mãi & Shop Trust (H8, H18, H19)
        if warranty >= 24 and return_days >= 15:
            activations.append(RuleActivation(
                rule_id="R3_TRUSTED_POST_SALES",
                rule_name="Chính sách Hậu mãi Đỉnh cao",
                category="recommendation",
                message=f"Bảo hành {warranty} tháng và đổi trả trong {return_days} ngày giúp nâng điểm Shop_Trust lên mức an tâm tối đa.",
                severity="success"
            ).to_dict())

        return activations
