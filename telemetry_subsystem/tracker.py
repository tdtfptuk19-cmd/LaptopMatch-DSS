"""
tracker.py - Telemetry Tracker: Ghi nhận sự kiện click nơi bán, lưu máy, ghim so sánh, sao chép cấu hình
Ẩn danh, không thu thập thông tin định danh cá nhân (PII), tuân thủ GDPR và đạo đức phần mềm (Alan Cooper).
"""
import json
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from laptopmatch_dss.data_subsystem.models import TelemetryEvent, UserFeedback

logger = logging.getLogger(__name__)

class TelemetryTracker:
    """Module theo dõi tương tác của người dùng để tính toán chỉ số RAR."""
    def __init__(self, db: Session):
        self.db = db

    def record_event(self, event_type: str, offer_id: Optional[str] = None, persona: str = "Q1", payload: Optional[Dict[str, Any]] = None) -> TelemetryEvent:
        """Ghi nhận sự kiện tương tác."""
        event = TelemetryEvent(
            event_type=event_type,
            offer_id=offer_id,
            persona=persona,
            payload_json=json.dumps(payload or {}, ensure_ascii=False)
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def record_feedback(self, offer_id: str, is_helpful: bool, persona: str = "Q1", rating: Optional[int] = None, comments: Optional[str] = None) -> UserFeedback:
        """Ghi nhận phản hồi chất lượng từ người dùng."""
        fb = UserFeedback(
            offer_id=offer_id,
            persona=persona,
            is_helpful=is_helpful,
            rating=rating,
            comments=comments
        )
        self.db.add(fb)
        self.db.commit()
        self.db.refresh(fb)
        return fb
