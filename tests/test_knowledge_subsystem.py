"""
test_knowledge_subsystem.py - Unit & Integration tests cho Knowledge-based Subsystem & UI (Giai đoạn 4 & 5)
Kiểm thử toàn diện:
1. Động cơ suy diễn Luật chuyên gia (ExpertRuleEngine): kích hoạt R1-R6
2. Động cơ Giải thích Quyết định Thông minh (DecisionExplainer): NLG, strengths, trade-offs
3. API Endpoint /api/explain/{offer_id}
4. API Endpoint /api/kpi/rar (Đo lường RAR theo R6)
5. Tính sẵn sàng của Giao diện Dashboard SPA 5 trang tại /dashboard/
"""
import pytest
from starlette.testclient import TestClient

from laptopmatch_dss.api.main import app
from laptopmatch_dss.knowledge_subsystem.rules import ExpertRuleEngine
from laptopmatch_dss.knowledge_subsystem.explanation import DecisionExplainer
from laptopmatch_dss.model_subsystem.scoring import load_persona

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

def test_expert_rule_engine_top1():
    """Kiểm tra luật chuyên gia kích hoạt cho offer Top-1 (OBS0164 - ASUS Zenbook 14)."""
    offer = {
        "offer_id": "OBS0164",
        "brand": "ASUS",
        "model": "Zenbook 14",
        "price_vnd": 24_500_000,
        "price_adv": 21.17,
        "weight_kg": 1.20,
        "battery_wh": 75.0,
        "warranty_months": 24,
        "return_days": 15,
        "dgpu": 0,
        "ram_gb": 16,
        "ssd_gb": 512
    }
    persona = load_persona("Q1")
    rules = ExpertRuleEngine.evaluate_offer_rules(offer, persona)
    rule_ids = [r["rule_id"] for r in rules]

    assert "R2_BARGAIN_DEAL" in rule_ids, "Phải kích hoạt luật R2: Deal hời >= 10%"
    assert "R4_ULTRAPORTABLE_FIT" in rule_ids, "Phải kích hoạt luật R4: Tối ưu di động mỏng nhẹ"
    assert "R3_TRUSTED_POST_SALES" in rule_ids, "Phải kích hoạt luật R3: Hậu mãi bảo hành 24 tháng"

def test_expert_rule_engine_overpriced_and_budget_advice():
    """Kiểm tra luật cảnh báo giá đắt (R2) và khuyến nghị ngân sách tối thiểu (R5)."""
    persona = load_persona("Q1")
    
    # Offer đắt hơn 15%
    overpriced_offer = {"price_adv": -15.0, "price_vnd": 28_000_000}
    rules_op = ExpertRuleEngine.evaluate_offer_rules(overpriced_offer, persona)
    assert any(r["rule_id"] == "R2_EXPENSIVE_WARNING" for r in rules_op)

    # Ngân sách dưới 20 triệu cho RAM 16GB
    low_budget_persona = {**persona, "budget": 18_000_000}
    offer_ram16 = {"price_adv": 5.0, "price_vnd": 17_500_000, "ram_gb": 16}
    rules_budget = ExpertRuleEngine.evaluate_offer_rules(offer_ram16, low_budget_persona)
    assert any(r["rule_id"] == "R5_MINIMUM_BUDGET_ADVICE" for r in rules_budget)

def test_decision_explainer():
    """Kiểm tra bộ sinh lời giải thích tự nhiên (DecisionExplainer)."""
    explainer = DecisionExplainer()
    offer = {
        "offer_id": "OBS0164",
        "brand": "ASUS",
        "model": "Zenbook 14 2025 Bạc",
        "seller_name": "SAZO",
        "price_vnd": 24_500_000,
        "fair_price": 31_841_187,
        "price_adv": 23.06,
        "utility": 0.8023,
        "deal": 0.8842,
        "dss_score": 0.8310,
        "weight_kg": 1.20,
        "battery_wh": 75.0,
        "ram_gb": 16,
        "ssd_gb": 512,
        "warranty_months": 24,
        "return_days": 15,
        "dgpu": 0
    }
    persona = load_persona("Q1")
    res = explainer.explain(offer, persona)

    assert "summary_headline" in res
    assert "natural_language_explanation" in res
    assert len(res["natural_language_explanation"]) > 50
    assert len(res["key_strengths"]) >= 3
    assert len(res["trade_offs"]) >= 1
    assert len(res["activated_rules"]) >= 1

def test_api_explain_endpoint(client):
    """Kiểm tra gọi API /api/explain/OBS0164."""
    response = client.get("/api/explain/OBS0164?persona_id=Q1")
    assert response.status_code == 200
    data = response.json()

    assert data["offer_id"] == "OBS0164"
    assert data["rank"] == 1
    assert data["dss_score"] >= 0.82
    assert "explanation" in data
    assert "natural_language_explanation" in data["explanation"]
    assert len(data["explanation"]["key_strengths"]) > 0

def test_api_kpi_rar_endpoint(client):
    """Kiểm tra gọi API /api/kpi/rar."""
    response = client.get("/api/kpi/rar")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active_monitoring"
    assert "total_telemetry_events" in data
    assert "recommendation_acceptance_rate_pct" in data

def test_dashboard_spa_served(client):
    """Kiểm tra giao diện Dashboard SPA 5 trang được phục vụ tại /dashboard/."""
    response = client.get("/dashboard/")
    assert response.status_code == 200
    html = response.text
    # Kiểm tra sự hiện diện của 5 tab
    assert "tab-overview" in html
    assert "tab-insights" in html
    assert "tab-pricing" in html
    assert "tab-simulator" in html
    assert "tab-ahp" in html
    assert "LaptopMatch DSS" in html
