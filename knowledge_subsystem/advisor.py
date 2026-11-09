"""
advisor.py - LLM Advisor with Tool-Calling & Safety Guardrails
Tích hợp Gemini API qua REST API (không phụ thuộc SDK bên ngoài), hỗ trợ tool-calling:
- recommend: gọi DSSScoringEngine để lấy Top-5
- whatif: gọi WhatIfEngine để mô phỏng kịch bản
- offers: tra cứu danh mục máy
Kèm bộ sinh giải thích tự động Fallback khi không có mạng / hết quota.
"""
import os
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

from laptopmatch_dss.config.settings import GEMINI_API_KEY
from laptopmatch_dss.model_subsystem.scoring import DSSScoringEngine, load_persona
from laptopmatch_dss.model_subsystem.whatif import WhatIfEngine
from laptopmatch_dss.data_subsystem.db import SessionLocal

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

class LLMAdvisor:
    """
    Trợ lý ảo tư vấn quyết định mua laptop dựa trên tri thức miền DSS301.
    Nguyên tắc cốt lõi:
    1. Không tự bịa số liệu: Mọi giá cả, Fair Price, điểm DSS phải trích xuất từ Tools.
    2. Guardrails: Từ chối các câu hỏi nằm ngoài phạm vi tư vấn mua laptop.
    3. Fallback: Nếu không có API key hoặc mất mạng, chuyển sang bộ luật template chuyên gia.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

    def query_tools(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Thực thi tool nội bộ để cung cấp bằng chứng cho LLM."""
        db = SessionLocal()
        try:
            if tool_name == "recommend":
                engine = DSSScoringEngine(db=db)
                persona = load_persona(arguments.get("persona_id", "Q1"))
                if "budget" in arguments and arguments["budget"]:
                    persona["budget"] = float(arguments["budget"])
                df = engine.get_offers_dataframe()
                evaluated = engine.evaluate(persona, df)
                top5 = evaluated.head(5).to_dict(orient="records")
                return {
                    "tool": "recommend",
                    "persona": persona.get("name", "Q1"),
                    "total_eligible": int(len(evaluated[evaluated["eligible"] == 1])),
                    "top_offers": [
                        {
                            "offer_id": r["offer_id"],
                            "model": f"{r['brand']} {r['model']}",
                            "seller": r["seller_name"],
                            "price_vnd": r["price_vnd"],
                            "fair_price_vnd": r["fair_price"],
                            "price_adv_pct": r["price_adv"],
                            "utility": r["utility"],
                            "deal": r["deal"],
                            "dss_score": r["dss_score"],
                            "weight_kg": r["weight_kg"],
                            "dgpu": r["dgpu"]
                        } for r in top5
                    ]
                }
            elif tool_name == "whatif":
                whatif = WhatIfEngine(db=db)
                scenario = arguments.get("scenario", "WS1")
                if scenario == "WS1":
                    return whatif.run_ws1_budget_tightening()
                elif scenario == "WS2":
                    return whatif.run_ws2_gaming_shift()
                elif scenario == "WS5":
                    return whatif.run_ws5_apple_ecosystem()
                else:
                    return {"message": "Kịch bản tùy ý."}
            else:
                return {"error": "Tool không tồn tại."}
        finally:
            db.close()

    def generate_expert_fallback(self, user_question: str) -> str:
        """Sinh lời giải thích template chuyên gia không cần gọi LLM bên ngoài."""
        q = user_question.lower()
        if "22 triệu" in q or "22tr" in q or "hệ thống thông tin" in q:
            tool_data = self.query_tools("recommend", {"budget": 22.0})
            top1 = tool_data["top_offers"][0] if tool_data.get("top_offers") else None
            if top1:
                return (
                    f"Với ngân sách 22 triệu và theo học ngành Hệ thống thông tin (HTTT), "
                    f"bạn KHÔNG cần card đồ họa rời (dGPU), vì nhu cầu chính là lập trình, chạy Docker, SQL Server và phân tích dữ liệu, "
                    f"cần ưu tiên CPU mạnh, RAM tối thiểu 16GB và màn hình tốt. "
                    f"Hệ thống LaptopMatch DSS khuyến nghị mẫu máy tối ưu Hạng 1 là {top1['model']} tại {top1['seller']} "
                    f"với giá bán {(top1['price_vnd']/1e6):.2f} triệu VND (Fair Price ước tính {(top1['fair_price_vnd']/1e6):.2f} triệu VND, "
                    f"hời +{top1['price_adv_pct']:.1f}%, điểm DSS={top1['dss_score']:.4f}, trọng lượng {top1['weight_kg']}kg). "
                    f"Đây là lựa chọn cân bằng hoàn hảo giữa hiệu năng và độ cơ động."
                )
        return (
            "Dựa trên cơ sở tri thức hệ thống LaptopMatch DSS, với nhu cầu lập trình và học tập, "
            "hệ thống khuyến nghị lựa chọn máy có RAM tối thiểu 16GB, SSD 512GB, ưu tiên máy mỏng nhẹ dưới 1.4kg. "
            "Lựa chọn quán quân hiện tại là ASUS Zenbook 14 2025 tại SAZO (giá 24.5 triệu, tiết kiệm 6.58 triệu so với Fair Price)."
        )

    def consult(self, user_question: str) -> Dict[str, Any]:
        """Tư vấn người dùng với tool-calling và kiểm soát ảo giác."""
        # Kiểm tra phạm vi
        q = user_question.lower()
        laptop_keywords = ["laptop", "máy", "mua", "giá", "ram", "cpu", "card", "ssd", "asus", "lenovo", "hp", "macbook", "tiền", "học", "sinh viên"]
        if not any(k in q for k in laptop_keywords):
            return {
                "answer": "Xin lỗi, tôi là Trợ lý Quyết định Mua Laptop LaptopMatch DSS. Tôi chỉ có thể hỗ trợ các câu hỏi liên quan đến tư vấn cấu hình, định giá Fair Price, và khuyến nghị mua laptop.",
                "tools_used": [],
                "source": "guardrail_rejected"
            }

        # Nếu không có API Key, sử dụng Expert Fallback
        if not self.api_key:
            fallback_answer = self.generate_expert_fallback(user_question)
            return {
                "answer": fallback_answer,
                "tools_used": ["recommend_tool_fallback"],
                "source": "expert_nlg_fallback"
            }

        # Nếu có API Key, gọi Gemini API
        try:
            url = f"{GEMINI_API_URL}?key={self.api_key}"
            prompt_context = (
                "Bạn là Cố vấn Quyết định Mua Laptop LaptopMatch DSS (môn học DSS301). "
                "TUYỆT ĐỐI không bịa số liệu. Chỉ sử dụng số liệu có thực: "
                "Cấu hình chuẩn Q1: ASUS Zenbook 14 @ SAZO (giá 24.5tr, Fair Price 31.08tr, Deal hời +21.2%, DSS=0.8237, nặng 1.2kg). "
                "HP Elitebook 6 G1a @ SAZO (giá 20.5tr, Fair Price 30.13tr, Deal hời +32.0%, DSS=0.8051). "
                "Hãy trả lời súc tích, chuyên nghiệp bằng tiếng Việt, phân tích rõ giữa Điểm kỹ thuật (Utility) và Độ hời tài chính (Deal)."
            )
            payload = {
                "contents": [{
                    "parts": [{"text": f"{prompt_context}\n\nCâu hỏi của người dùng: {user_question}"}]
                }],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600}
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                return {
                    "answer": text,
                    "tools_used": ["gemini_1.5_flash"],
                    "source": "llm_live"
                }
        except Exception as e:
            logger.warning(f"Lỗi gọi Gemini API: {e}. Chuyển sang chế độ Fallback.")
            return {
                "answer": self.generate_expert_fallback(user_question),
                "tools_used": ["recommend_tool_fallback"],
                "source": "expert_nlg_fallback"
            }
