"""
explanation.py - Động cơ Giải thích Quyết định Thông minh (Knowledge-based Subsystem)
Tích hợp:
1. Gemini API (qua httpx REST call không phụ thuộc SDK nặng)
2. Bộ sinh ngôn ngữ tự nhiên chuyên gia (Deterministic NLG & Expert Rules Fallback)
Sinh lời giải thích súc tích (3-4 câu) bằng tiếng Việt cho người dùng:
"Tại sao chiếc máy này được hệ thống LaptopMatch DSS đề xuất?"
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
import httpx

from laptopmatch_dss.config.settings import GEMINI_API_KEY
from laptopmatch_dss.knowledge_subsystem.rules import ExpertRuleEngine

logger = logging.getLogger(__name__)

class DecisionExplainer:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

    def explain(self, offer: Dict[str, Any], persona: Dict[str, Any], market_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Sinh nội dung giải thích đa tầng cho offer được chọn.
        """
        # 1. Đánh giá hệ luật chuyên gia
        activated_rules = ExpertRuleEngine.evaluate_offer_rules(offer, persona, market_context)

        # 2. Xây dựng điểm mạnh và điểm đánh đổi
        strengths, trade_offs = self._extract_strengths_and_tradeoffs(offer, persona)

        # 3. Thử gọi Gemini API nếu có API key
        if self.api_key and len(self.api_key.strip()) > 10:
            ai_explanation = self._call_gemini_api(offer, persona, strengths, trade_offs)
            if ai_explanation:
                return {
                    "source": "gemini_api",
                    "summary_headline": ai_explanation.get("headline", f"Lựa chọn tối ưu nhất theo hồ sơ {persona.get('name', 'Q1')}"),
                    "natural_language_explanation": ai_explanation.get("explanation", ""),
                    "key_strengths": strengths,
                    "trade_offs": trade_offs,
                    "activated_rules": activated_rules
                }

        # 4. Fallback sinh lời giải thích bằng Động cơ NLG chuyên gia
        nlg_result = self._generate_expert_nlg(offer, persona, strengths, trade_offs, activated_rules)
        return {
            "source": "expert_rule_engine",
            "summary_headline": nlg_result["headline"],
            "natural_language_explanation": nlg_result["explanation"],
            "key_strengths": strengths,
            "trade_offs": trade_offs,
            "activated_rules": activated_rules
        }

    def _extract_strengths_and_tradeoffs(self, offer: Dict[str, Any], persona: Dict[str, Any]) -> tuple[List[str], List[str]]:
        strengths = []
        trade_offs = []

        price_adv = float(offer.get("price_adv", offer.get("price_adv_pct", 0.0)))
        price_vnd = float(offer.get("price_vnd", 0.0))
        fair_price = float(offer.get("fair_price", offer.get("fair_price_vnd", price_vnd)))
        savings = fair_price - price_vnd
        weight = float(offer.get("weight_kg", 2.0))
        battery = float(offer.get("battery_wh", 50.0))
        ram = int(offer.get("ram_gb", 16))
        ssd = int(offer.get("ssd_gb", 512))
        warranty = int(offer.get("warranty_months", 12))
        dgpu = int(offer.get("dgpu", 0))

        # Điểm mạnh
        if savings > 1_000_000:
            strengths.append(f"Mức giá cực hời: Tiết kiệm {savings/1e6:.1f} triệu VND ({price_adv:+.1f}%) so với giá trị thực tế.")
        elif price_adv >= 0:
            strengths.append(f"Giá bán sát giá trị thực tế của cấu hình (Adv: {price_adv:+.1f}%).")

        if weight <= 1.3:
            strengths.append(f"Thiết kế siêu mỏng nhẹ ({weight:.2f} kg), tối ưu 100% cho việc mang vác di chuyển.")
        elif weight <= 1.6:
            strengths.append(f"Trọng lượng gọn gàng ({weight:.2f} kg), vừa vặn cho nhu cầu học tập và làm việc.")

        if battery >= 70:
            strengths.append(f"Dung lượng pin lớn ({battery:.0f} Wh), đáp ứng tốt cả ngày sử dụng không cần sạc.")

        if ram >= 32:
            strengths.append(f"Bộ nhớ RAM khủng {ram} GB cho khả năng đa nhiệm và chạy máy ảo/container thoải mái.")
        elif ram >= 16:
            strengths.append(f"RAM {ram} GB chuẩn mực cho lập trình và ứng dụng đồ họa.")

        if warranty >= 24:
            strengths.append(f"Chính sách bảo hành dài hạn {warranty} tháng chính hãng mang lại sự an tâm tuyệt đối.")

        # Điểm đánh đổi
        if dgpu == 0:
            trade_offs.append("Sử dụng đồ họa tích hợp iGPU: tối ưu thời lượng pin và tản nhiệt, nhưng không phù hợp cho game 3D AAA đồ họa nặng.")
        else:
            trade_offs.append(f"Trang bị card đồ họa rời RTX mạnh mẽ nhưng hy sinh tính di động (trọng lượng {weight:.2f} kg).")

        if price_adv < -5.0:
            trade_offs.append(f"Giá bán tại cửa hàng này cao hơn giá trị ước tính {abs(price_adv):.1f}%, nên cân nhắc so sánh các nhà bán khác.")

        if ssd <= 512:
            trade_offs.append("Ổ cứng SSD 512GB vừa đủ cho tác vụ hiện tại, có thể cần nâng cấp hoặc dùng ổ cứng ngoài về sau.")

        return strengths, trade_offs

    def _generate_expert_nlg(self, offer: Dict[str, Any], persona: Dict[str, Any], strengths: List[str], trade_offs: List[str], rules: List[Dict[str, Any]]) -> Dict[str, str]:
        brand = offer.get("brand", "")
        model = offer.get("model", "")
        seller = offer.get("seller_name", offer.get("seller_id", ""))
        price_m = float(offer.get("price_vnd", 0.0)) / 1e6
        fair_price_m = float(offer.get("fair_price", offer.get("fair_price_vnd", 0.0))) / 1e6
        adv = float(offer.get("price_adv", offer.get("price_adv_pct", 0.0)))
        dss = float(offer.get("dss_score", 0.0))
        weight = float(offer.get("weight_kg", 1.5))
        ram = int(offer.get("ram_gb", 16))

        headline = f"{brand} {model} tại {seller} – Lựa chọn số 1 cân bằng Hoàn hảo giữa Hiệu năng và Giá trị"

        adv_text = f"tiết kiệm {fair_price_m - price_m:.1f} triệu VND (rẻ hơn {adv:.1f}% so với giá trị thực tế {fair_price_m:.1f} triệu)" if adv > 0 else f"mức giá hợp lý {price_m:.2f} triệu"

        explanation = (
            f"Hệ thống LaptopMatch DSS đề xuất {brand} {model} bán tại {seller} là lựa chọn tối ưu nhất "
            f"với điểm tổng hợp DSS_Score đạt {dss:.3f}. "
            f"Ở mức giá {price_m:.2f} triệu VND, máy giúp bạn {adv_text}, "
            f"đồng thời đáp ứng vượt trội tiêu chuẩn của hồ sơ {persona.get('name', 'Q1')} nhờ trọng lượng nhẹ chỉ {weight:.2f}kg và RAM {ram}GB. "
            f"Chính sách bảo hành chu đáo tại {seller} hoàn thiện điểm số Deal, biến đây thành lựa chọn mua sắm kinh tế và tin cậy nhất hiện tại."
        )

        return {"headline": headline, "explanation": explanation}

    def _call_gemini_api(self, offer: Dict[str, Any], persona: Dict[str, Any], strengths: List[str], trade_offs: List[str]) -> Optional[Dict[str, str]]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        prompt = f"""
Bạn là chuyên gia tư vấn quyết định mua sắm laptop của hệ thống LaptopMatch DSS.
Hãy giải thích ngắn gọn, thuyết phục và trung thực cho người dùng lý do mẫu laptop sau được thuật toán xếp Hạng 1.

THÔNG TIN CHI TIẾT:
- Tên máy: {offer.get('brand')} {offer.get('model')}
- Nơi bán: {offer.get('seller_name', offer.get('seller_id'))}
- Giá bán: {float(offer.get('price_vnd', 0))/1e6:.2f} triệu VND
- Fair Price (Giá trị thực tế): {float(offer.get('fair_price', 0))/1e6:.2f} triệu VND
- Chênh lệch giá (Advantage): {float(offer.get('price_adv', 0)):+.1f}%
- Điểm DSS: {float(offer.get('dss_score', 0)):.3f} (Utility: {float(offer.get('utility', 0)):.3f}, Deal: {float(offer.get('deal', 0)):.3f})
- Cấu hình: CPU {offer.get('cpu')}, RAM {offer.get('ram_gb')}GB, SSD {offer.get('ssd_gb')}GB, Nặng {offer.get('weight_kg')}kg, Pin {offer.get('battery_wh')}Wh
- Bảo hành: {offer.get('warranty_months')} tháng
- Hồ sơ người dùng: {persona.get('name')}

YÊU CẦU:
1. Tiêu đề (headline) súc tích.
2. Đoạn văn giải thích (explanation) bằng tiếng Việt tự nhiên, dài đúng 3-4 câu, nêu rõ vì sao máy thỏa mãn nhu cầu và tại sao đây là món hời kinh tế.
3. Trả về đúng định dạng JSON: {{"headline": "...", "explanation": "..."}}. Không thêm markdown ngoài JSON.
"""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
        }
        try:
            with httpx.Client(timeout=6.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(text)
                    return parsed
        except Exception as e:
            logger.warning(f"Không thể gọi Gemini API (sử dụng fallback NLG): {e}")
            return None
        return None
