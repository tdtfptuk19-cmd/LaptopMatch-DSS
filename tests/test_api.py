"""
test_api.py - Unit & Integration tests cho Backend API (Giai đoạn 3)
Kiểm thử toàn diện:
1. Endpoint /api/health và Middleware độ trễ (X-Process-Time-Ms)
2. Endpoint /api/recommend: kiểm tra hồi quy Q1 (OBS0164, 103 eligible, Top 5)
3. Endpoint /api/ahp/calculate: ma trận nhất quán và ma trận bất nhất
4. Endpoint /api/whatif: các kịch bản WS1-WS5 và kịch bản tùy biến
5. Endpoint /api/models/hedonic: thông số mô hình và hệ số beta
6. Endpoint /api/telemetry & /api/feedback: ghi nhận hành vi đo lường RAR (R6)
7. OpenAPI Schema: kiểm tra tài liệu tự động /openapi.json
"""
import pytest
from starlette.testclient import TestClient

from laptopmatch_dss.api.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

def test_health_check(client):
    """Kiểm tra endpoint sức khỏe và header độ trễ."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["dim_sellers_count"] == 6
    assert data["fact_offers_count"] >= 210
    assert "X-Process-Time-Ms" in response.headers

def test_recommend_q1_regression(client):
    """BÀI KIỂM TRA HỒI QUY: /api/recommend với persona Q1 phải cho ra kết quả chuẩn ASM2."""
    payload = {"persona_id": "Q1", "top_n": 10}
    response = client.post("/api/recommend", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["total_eligible"] == 103
    assert len(data["top_offers"]) == 10

    # Top 1 phải là OBS0164 @ SAZO
    top1 = data["top_offers"][0]
    assert top1["rank"] == 1
    assert top1["offer_id"] == "OBS0164"
    assert top1["brand"] == "ASUS"
    assert "Zenbook 14" in top1["model"]
    assert top1["seller_id"] == "SAZO"
    assert top1["price_vnd"] == 24_500_000
    assert abs(top1["utility"] - 0.8023) < 0.001
    assert abs(top1["deal"] - 0.8635) < 0.001
    assert abs(top1["dss_score"] - 0.8237) < 0.001
    assert top1["expensive_warning"] is False

    # Điểm tiêu chí S_k
    assert "cpu" in top1["criteria_scores"]
    assert "ram" in top1["criteria_scores"]
    assert "w" in top1["criteria_scores"]

    # Kiểm tra thứ tự Top 5
    top5_ids = [o["offer_id"] for o in data["top_offers"][:5]]
    assert top5_ids == ["OBS0164", "OBS0202", "OBS0128", "OBS0181", "OBS0144"]

def test_recommend_with_custom_filters(client):
    """Kiểm tra gợi ý với bộ lọc tùy biến (ngân sách 20tr, lọc hãng Apple)."""
    # Lọc ngân sách 20tr
    res_budget = client.post("/api/recommend", json={"persona_id": "Q1", "budget": 20_000_000})
    assert res_budget.status_code == 200
    data_budget = res_budget.json()
    assert data_budget["total_eligible"] == 20

    # Lọc thương hiệu Apple
    res_apple = client.post("/api/recommend", json={"persona_id": "Q1", "brand": "Apple", "budget": 36_000_000})
    assert res_apple.status_code == 200
    data_apple = res_apple.json()
    assert all(o["brand"] == "Apple" for o in data_apple["top_offers"])

def test_ahp_endpoint_consistent_and_inconsistent(client):
    """Kiểm tra endpoint tính toán trọng số AHP."""
    # Ma trận nhất quán
    consistent_payload = {
        "criteria": ["cpu", "ram", "w"],
        "matrix": [
            [1.0, 2.0, 0.5],
            [0.5, 1.0, 0.25],
            [2.0, 4.0, 1.0]
        ]
    }
    res_good = client.post("/api/ahp/calculate", json=consistent_payload)
    assert res_good.status_code == 200
    data_good = res_good.json()
    assert data_good["is_consistent"] is True
    assert data_good["consistency_ratio"] < 0.10
    assert abs(sum(data_good["weights"].values()) - 1.0) < 1e-5

    # Ma trận bất nhất
    inconsistent_payload = {
        "criteria": ["cpu", "ram", "w"],
        "matrix": [
            [1.0, 9.0, 1/9],
            [1/9, 1.0, 9.0],
            [9.0, 1/9, 1.0]
        ]
    }
    res_bad = client.post("/api/ahp/calculate", json=inconsistent_payload)
    assert res_bad.status_code == 200
    data_bad = res_bad.json()
    assert data_bad["is_consistent"] is False
    assert data_bad["consistency_ratio"] >= 0.10
    assert data_bad["warning"] is not None

def test_whatif_endpoints(client):
    """Kiểm tra các kịch bản What-if qua API."""
    # WS1
    res_ws1 = client.post("/api/whatif", json={"scenario_type": "WS1"})
    assert res_ws1.status_code == 200
    assert res_ws1.json()["details"]["30tr"]["eligible_count"] == 103
    assert res_ws1.json()["details"]["20tr"]["eligible_count"] == 20

    # WS2
    res_ws2 = client.post("/api/whatif", json={"scenario_type": "WS2"})
    assert res_ws2.status_code == 200
    assert res_ws2.json()["details"]["top1"]["brand"] == "MSI"

    # WS3
    res_ws3 = client.post("/api/whatif", json={"scenario_type": "WS3", "discount_cut_pct": 6.9})
    assert res_ws3.status_code == 200
    steps = {s["discount_pct"]: s for s in res_ws3.json()["details"]}
    assert steps[6.9]["rank"] == 1

def test_hedonic_model_metadata_endpoint(client):
    """Kiểm tra lấy metadata mô hình định giá Hedonic."""
    response = client.get("/api/models/hedonic")
    assert response.status_code == 200
    data = response.json()
    assert data["sample_size"] == 209
    assert data["r_squared"] >= 0.80
    assert data["mape_5fold_pct"] <= 15.0
    assert "cpu_k" in data["coefficients"]
    assert "gpu_k" in data["coefficients"]
    assert "weight_kg" in data["coefficients"]

def test_telemetry_and_feedback_endpoints(client):
    """Kiểm tra ghi nhận sự kiện telemetry và đánh giá người dùng (R6)."""
    # Telemetry
    telemetry_payload = {
        "event_type": "view_seller",
        "offer_id": "OBS0164",
        "persona": "Q1",
        "payload": {"source_button": "compare_table"}
    }
    res_tel = client.post("/api/telemetry", json=telemetry_payload)
    assert res_tel.status_code == 200
    assert res_tel.json()["status"] == "recorded"
    assert res_tel.json()["event_id"] > 0

    # Feedback
    feedback_payload = {
        "offer_id": "OBS0164",
        "persona": "Q1",
        "is_helpful": True,
        "rating": 5,
        "comments": "Gợi ý rất chuẩn và tiết kiệm được hơn 6 triệu!"
    }
    res_fb = client.post("/api/feedback", json=feedback_payload)
    assert res_fb.status_code == 200
    assert res_fb.json()["status"] == "recorded"
    assert res_fb.json()["feedback_id"] > 0

def test_openapi_json(client):
    """Kiểm tra tính hợp lệ của tài liệu OpenAPI tự động."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert "/api/recommend" in schema["paths"]
    assert "/api/ahp/calculate" in schema["paths"]
    assert "/api/whatif" in schema["paths"]
    assert "/api/models/hedonic" in schema["paths"]
    assert "/api/telemetry" in schema["paths"]
    assert "/api/feedback" in schema["paths"]
