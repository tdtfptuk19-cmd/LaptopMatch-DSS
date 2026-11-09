"""
test_telemetry.py - Unit tests cho Telemetry Subsystem & Đo lường chỉ số RAR
Kiểm thử:
1. Ghi nhận các sự kiện người dùng (view_seller, save_laptop, pin_compare, copy_config)
2. Ghi nhận phản hồi người dùng (UserFeedback)
3. Tính toán chính xác tỷ lệ chấp nhận khuyến nghị (RAR action & RAR feedback)
"""
import pytest
from laptopmatch_dss.data_subsystem.db import SessionLocal, init_db
from laptopmatch_dss.telemetry_subsystem.tracker import TelemetryTracker
from laptopmatch_dss.telemetry_subsystem.rar_calculator import RARCalculator

@pytest.fixture(scope="module")
def db_session():
    init_db()
    session = SessionLocal()
    yield session
    session.close()

def test_telemetry_event_recording(db_session):
    """Kiểm tra ghi nhận sự kiện tương tác người dùng."""
    tracker = TelemetryTracker(db=db_session)
    event = tracker.record_event(
        event_type="view_seller",
        offer_id="OBS0164",
        persona="Q1",
        payload={"seller_id": "SAZO", "target_url": "https://sazo.vn/test"}
    )

    assert event.event_id is not None
    assert event.event_type == "view_seller"
    assert event.offer_id == "OBS0164"

def test_user_feedback_recording(db_session):
    """Kiểm tra ghi nhận đánh giá hài lòng từ người dùng."""
    tracker = TelemetryTracker(db=db_session)
    fb = tracker.record_feedback(
        offer_id="OBS0164",
        is_helpful=True,
        persona="Q1",
        rating=5,
        comments="Gợi ý rất chuẩn với sinh viên lập trình!"
    )

    assert fb.feedback_id is not None
    assert fb.is_helpful is True
    assert fb.rating == 5

def test_rar_calculation(db_session):
    """Kiểm tra công thức tính RAR theo R6."""
    tracker = TelemetryTracker(db=db_session)
    # Thêm một vài event giả lập
    tracker.record_event("view_seller", "OBS0164", "Q1")
    tracker.record_event("save_laptop", "OBS0202", "Q1")
    tracker.record_event("copy_config", "OBS0128", "Q1")

    tracker.record_feedback("OBS0164", True, "Q1")
    tracker.record_feedback("OBS0202", True, "Q1")

    calc = RARCalculator(db=db_session)
    res = calc.calculate_rar(persona="Q1")

    assert res["total_events"] >= 3
    assert res["actions"]["view_seller"] >= 1
    assert res["rar_action_pct"] > 0.0
    assert res["rar_feedback_pct"] > 0.0
