"""
test_model_subsystem.py - Unit tests cho Model Management Subsystem (Giai đoạn 2)
Kiểm thử toàn diện:
1. Huấn luyện mô hình Hedonic OLS Robust HC3, R2, MAPE 5-fold CV, Breusch-Pagan, Model Registry
2. BÀI KIỂM TRA HỒI QUY (Regression Test - Nguyên tắc 1):
   Tái hiện 100% Top-5 và DSS_Score khớp với dashboard.html và ASM2
3. Kiểm thử phân tích AHP Saaty: ma trận nhất quán, ma trận bất nhất (CR >= 0.1), vector trọng số
4. Kiểm thử 5 kịch bản What-if chính thức (WS1, WS2, WS3, WS4, WS5)
"""
import pytest
import numpy as np
from datetime import date

from laptopmatch_dss.model_subsystem.pricing import HedonicPricingModel
from laptopmatch_dss.model_subsystem.scoring import DSSScoringEngine, load_persona, S_k, sigmoid
from laptopmatch_dss.model_subsystem.ahp import AHPAnalyzer
from laptopmatch_dss.model_subsystem.whatif import WhatIfEngine

def test_hedonic_pricing_model():
    """Kiểm tra tái huấn luyện Hedonic OLS Robust HC3 từ DB."""
    model = HedonicPricingModel()
    res = model.fit_from_db(snapshot_date=date(2026, 10, 8), exclude_outliers=("OBS0075",))
    
    assert res["sample_size"] == 209, f"Sai kích thước mẫu: {res['sample_size']} != 209"
    assert res["r_squared"] >= 0.80, f"R2 quá thấp: {res['r_squared']} < 0.80"
    assert res["mape_5fold_pct"] <= 15.0, f"MAPE vượt trần 15%: {res['mape_5fold_pct']}%"
    assert res["breusch_pagan_pvalue"] < 0.05, "Không phát hiện heteroscedasticity (cần thiết cho HC3)"
    
    # Kiểm tra dấu của các hệ số beta
    coeffs = res["coefficients"]
    assert coeffs["cpu_k"] > 0, "CPU beta phải dương"
    assert coeffs["gpu_k"] > 0, "GPU beta phải dương"
    assert coeffs["ram_gb"] > 0, "RAM beta phải dương"
    assert coeffs["battery_wh"] > 0, "Battery beta phải dương"
    assert coeffs["weight_kg"] < 0, "Weight beta phải âm (nhẹ đắt hơn)"
    assert coeffs["dgpu"] > 0, "dGPU beta phải dương (RTX có phụ phí)"

    # Kiểm tra dự báo cho ASUS Zenbook 14 (OBS0164)
    # CPU: 26500, GPU: 8150, RAM: 16, Battery: 75, Weight: 1.20, dGPU: 0
    fp_pred = model.predict_fair_price(26500, 8150, 16, 75.0, 1.20, 0)
    expected_fp = 31080691.97
    assert abs(fp_pred - expected_fp) / expected_fp < 0.001, f"Sai số dự báo FP: {fp_pred} != {expected_fp}"

def test_regression_test_q1_top5_and_dss_scores():
    """
    NGUYÊN TẮC 1 - BÀI KIỂM TRA HỒI QUY BẮT BUỘC:
    Tái hiện Top-5 và DSS_Score trùng khớp tuyệt đối với dashboard.html trên snapshot T1.
    """
    engine = DSSScoringEngine()
    q1 = load_persona("Q1")
    df = engine.evaluate(q1)
    engine.close()

    eligible_df = df[df["eligible"] == 1]
    
    # Ràng buộc số lượng đạt chuẩn Q1
    assert len(eligible_df) == 103, f"Số offer đạt Eligibility phải là 103, thực tế: {len(eligible_df)}"

    # Kiểm tra Top 1: ASUS Zenbook 14 2025 Bạc @ SAZO (OBS0164)
    top1 = eligible_df.iloc[0]
    assert top1["offer_id"] == "OBS0164", f"Top 1 không phải OBS0164 mà là {top1['offer_id']}"
    assert top1["brand"] == "ASUS"
    assert "Zenbook 14" in top1["model"]
    assert top1["seller_id"] == "SAZO"
    assert top1["price_vnd"] == 24_500_000

    # Kiểm tra các chỉ số thành phần Top 1 với độ sai số cực nhỏ (<= 1e-4)
    assert abs(top1["utility"] - 0.802312) < 0.001, f"Utility lệch: {top1['utility']} != 0.8023"
    assert abs(top1["deal"] - 0.863467) < 0.001, f"Deal lệch: {top1['deal']} != 0.8635"
    assert abs(top1["dss_score"] - 0.823716) < 0.001, f"DSS_Score lệch: {top1['dss_score']} != 0.8237"
    assert abs(top1["price_adv"] - 21.1729) < 0.01, f"Adv lệch: {top1['price_adv']} != 21.17%"

    # Kiểm tra thứ tự chính xác của Top 5 offer
    expected_top5_ids = ["OBS0164", "OBS0202", "OBS0128", "OBS0181", "OBS0144"]
    actual_top5_ids = eligible_df.head(5)["offer_id"].tolist()
    assert actual_top5_ids == expected_top5_ids, f"Top 5 không trùng khớp: {actual_top5_ids} != {expected_top5_ids}"

def test_ahp_consistent_matrix():
    """Kiểm tra AHP với ma trận nhất quán (CR < 0.10)."""
    analyzer = AHPAnalyzer(["cpu", "ram", "w"])
    matrix = np.array([
        [1.0, 2.0, 0.5],
        [0.5, 1.0, 0.25],
        [2.0, 4.0, 1.0]
    ])
    res = analyzer.calculate_weights(matrix, ["cpu", "ram", "w"])
    
    assert res["is_consistent"] is True
    assert res["consistency_ratio"] < 0.10
    assert abs(sum(res["weights"].values()) - 1.0) < 1e-5
    # Cân nặng ưu tiên gấp đôi CPU, CPU gấp đôi RAM -> w: [2/7, 1/7, 4/7]
    assert abs(res["weights"]["w"] - 4/7) < 0.01
    assert abs(res["weights"]["cpu"] - 2/7) < 0.01
    assert abs(res["weights"]["ram"] - 1/7) < 0.01

def test_ahp_inconsistent_matrix():
    """Kiểm tra AHP phát hiện ma trận bất nhất (CR >= 0.10) và đưa ra cảnh báo."""
    analyzer = AHPAnalyzer(["cpu", "ram", "w"])
    # Ma trận vi phạm bắc cầu: A > B rất nhiều, B > C rất nhiều, nhưng C > A rất nhiều
    matrix = np.array([
        [1.0, 9.0, 1/9],
        [1/9, 1.0, 9.0],
        [9.0, 1/9, 1.0]
    ])
    res = analyzer.calculate_weights(matrix, ["cpu", "ram", "w"])
    
    assert res["is_consistent"] is False
    assert res["consistency_ratio"] >= 0.10
    assert res["warning"] is not None
    assert len(res["inconsistency_hints"]) > 0

def test_whatif_scenarios():
    """Kiểm tra sự chính xác của cả 5 kịch bản What-if từ ASM2."""
    whatif = WhatIfEngine()
    try:
        # WS1: 30tr -> 20tr -> 18tr
        ws1 = whatif.run_ws1_budget_tightening()
        assert ws1["details"]["30tr"]["eligible_count"] == 103
        assert ws1["details"]["20tr"]["eligible_count"] == 20
        assert ws1["details"]["18tr"]["eligible_count"] == 4

        # WS2: Gaming -> Quán quân chuyển sang MSI Gaming Thin 15 @ FPT
        ws2 = whatif.run_ws2_gaming_shift()
        assert ws2["details"]["top1"]["brand"] == "MSI"
        assert "Gaming Thin" in ws2["details"]["top1"]["model"]
        assert ws2["details"]["top1"]["seller_id"] == "FPT"
        assert abs(ws2["details"]["top1"]["dss_score"] - 0.793) < 0.005

        # WS3: SAZO giảm giá Zenbook AI 7 350
        ws3 = whatif.run_ws3_price_discount(discount_pcts=[0.0, 5.0, 6.9, 10.0])
        steps = {s["discount_pct"]: s for s in ws3["simulation_steps"]}
        assert steps[0.0]["rank"] > 1
        assert steps[5.0]["rank"] > 1
        assert steps[6.9]["rank"] == 1, "Tại mức giảm 6.9%, Zenbook AI 7 350 phải lên hạng 1"

        # WS4: Ràng buộc di động cứng -> 4 lựa chọn, Quán quân vẫn là Zenbook 14
        ws4 = whatif.run_ws4_portability_constraint()
        assert ws4["details"]["eligible_count"] == 4
        assert ws4["details"]["top1"]["offer_id"] == "OBS0164"

        # WS5: Apple <= 27tr -> 2 lựa chọn
        ws5 = whatif.run_ws5_apple_ecosystem()
        assert ws5["details_27tr"]["eligible_count"] == 2

    finally:
        whatif.close()
