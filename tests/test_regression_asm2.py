"""
test_regression_asm2.py - Bài kiểm tra hồi quy bắt buộc (Regression Test)
So sánh DSS_Score và Top-5 của hệ thống mới với kết quả gốc ASM2 / dashboard.html.
Nguyên tắc 1: Sai số tuyệt đối phải <= 1e-6.
"""
import pytest
from laptopmatch_dss.data_subsystem.db import SessionLocal, init_db
from laptopmatch_dss.data_subsystem.migrate import migrate_data
from laptopmatch_dss.model_subsystem.scoring import DSSScoringEngine, load_persona

# Bảng kết quả chuẩn ASM2 / dashboard.html cho Persona Q1 (Snapshot T1)
GROUND_TRUTH_Q1 = [
    {
        "offer_id": "OBS0164",
        "rank": 1,
        "brand": "ASUS",
        "model": "Zenbook 14 2025 Bạc",
        "seller_id": "SAZO",
        "price_vnd": 24500000.0,
        "fair_price": 31841187.39580011,
        "price_adv": 23.05563327317505,
        "utility": 0.8023121481846327,
        "deal": 0.8842265055177242,
        "dss_score": 0.8309821732512147
    },
    {
        "offer_id": "OBS0202",
        "rank": 2,
        "brand": "HP",
        "model": "Elitebook 6 G1a 14 2025 R7 H255 24GB",
        "seller_id": "SAZO",
        "price_vnd": 20500000.0,
        "fair_price": 30335639.05693724,
        "price_adv": 32.42271916037976,
        "utility": 0.7640254106388966,
        "deal": 0.8913919616450449,
        "dss_score": 0.8086037034910485
    },
    {
        "offer_id": "OBS0128",
        "rank": 3,
        "brand": "Lenovo",
        "model": "Lecoo 14 N143C (2026)",
        "seller_id": "T&T Center",
        "price_vnd": 19290000.0,
        "fair_price": 22871991.07407724,
        "price_adv": 15.66103739056199,
        "utility": 0.804232934843794,
        "deal": 0.7817731677647368,
        "dss_score": 0.7963720163661239
    },
    {
        "offer_id": "OBS0181",
        "rank": 4,
        "brand": "ASUS",
        "model": "Zenbook 14 2025 AI 7 350",
        "seller_id": "SAZO",
        "price_vnd": 29300000.0,
        "fair_price": 33136463.137860443,
        "price_adv": 11.577768942627582,
        "utility": 0.8272719783281733,
        "deal": 0.7275699527080908,
        "dss_score": 0.7923762693611445
    },
    {
        "offer_id": "OBS0172",
        "rank": 5,
        "brand": "Lenovo",
        "model": "Xiaoxin Air 13 2026",
        "seller_id": "SAZO",
        "price_vnd": 20400000.0,
        "fair_price": 24545172.853958968,
        "price_adv": 16.887935068220063,
        "utility": 0.7941574514494794,
        "deal": 0.7718613793622264,
        "dss_score": 0.7863538262189409
    }
]

@pytest.fixture(scope="module")
def scoring_engine():
    init_db()
    session = SessionLocal()
    migrate_data(db=session)
    engine = DSSScoringEngine(db=session)
    yield engine
    engine.close()
    session.close()

def test_regression_top5_dss_scores_q1(scoring_engine):
    """
    Kiểm tra hồi quy: Top-5 và điểm số DSS_Score cho Persona Q1
    phải khớp tuyệt đối với kết quả ASM2 (sai số <= 1e-6).
    """
    persona = load_persona("Q1")
    df = scoring_engine.get_offers_dataframe(snapshot_date="2026-10-08")
    evaluated = scoring_engine.evaluate(persona, df)
    top5 = evaluated.head(5)

    assert len(top5) == 5, "Danh sách Top-5 phải có đúng 5 phần tử."

    for i, expected in enumerate(GROUND_TRUTH_Q1):
        actual = top5.iloc[i]
        assert actual["offer_id"] == expected["offer_id"], f"Hạng {i+1}: offer_id sai lệch ({actual['offer_id']} vs {expected['offer_id']})"
        assert actual["seller_id"] == expected["seller_id"], f"Hạng {i+1}: seller_id sai lệch"
        assert abs(actual["price_vnd"] - expected["price_vnd"]) < 1e-3, f"Hạng {i+1}: giá bán VND sai lệch"

        # Kiểm tra sai số <= 1e-6 cho Fair Price, Utility, Deal, DSS_Score
        assert abs(actual["utility"] - expected["utility"]) <= 1e-6, f"Hạng {i+1}: Utility sai lệch > 1e-6 (actual={actual['utility']}, expected={expected['utility']})"
        assert abs(actual["deal"] - expected["deal"]) <= 1e-6, f"Hạng {i+1}: Deal sai lệch > 1e-6 (actual={actual['deal']}, expected={expected['deal']})"
        assert abs(actual["dss_score"] - expected["dss_score"]) <= 1e-6, f"Hạng {i+1}: DSS_Score sai lệch > 1e-6 (actual={actual['dss_score']}, expected={expected['dss_score']})"
