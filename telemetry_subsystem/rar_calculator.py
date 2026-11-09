"""
rar_calculator.py - Recommendation Acceptance Rate (RAR) Calculator
Thực hiện tính toán tỷ lệ chấp nhận khuyến nghị theo thời gian và theo Persona (Khuyến nghị R6).
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from laptopmatch_dss.data_subsystem.models import TelemetryEvent, UserFeedback

logger = logging.getLogger(__name__)

class RARCalculator:
    """Công cụ đo lường và báo cáo chỉ số RAR (Recommendation Acceptance Rate)."""
    def __init__(self, db: Session):
        self.db = db

    def calculate_rar(self, persona: Optional[str] = None) -> Dict[str, Any]:
        """
        Tính toán chỉ số RAR:
        - RAR_Action (% người dùng click 'Xem nơi bán' hoặc 'Lưu máy' trên tổng số tương tác)
        - RAR_Feedback (% người dùng đánh giá khuyến nghị là 'Hữu ích')
        """
        q_events = self.db.query(TelemetryEvent)
        q_feedbacks = self.db.query(UserFeedback)

        if persona:
            q_events = q_events.filter(TelemetryEvent.persona == persona)
            q_feedbacks = q_feedbacks.filter(UserFeedback.persona == persona)

        total_events = q_events.count()
        view_seller = q_events.filter(TelemetryEvent.event_type == "view_seller").count()
        save_laptop = q_events.filter(TelemetryEvent.event_type == "save_laptop").count()
        copy_config = q_events.filter(TelemetryEvent.event_type == "copy_config").count()
        pin_compare = q_events.filter(TelemetryEvent.event_type == "pin_compare").count()

        feedbacks = q_feedbacks.all()
        total_fb = len(feedbacks)
        helpful_fb = sum(1 for f in feedbacks if f.is_helpful)

        rar_action_pct = round((view_seller + save_laptop) / total_events * 100.0, 1) if total_events > 0 else 0.0
        rar_feedback_pct = round(helpful_fb / total_fb * 100.0, 1) if total_fb > 0 else 0.0

        return {
            "total_events": total_events,
            "actions": {
                "view_seller": view_seller,
                "save_laptop": save_laptop,
                "copy_config": copy_config,
                "pin_compare": pin_compare
            },
            "rar_action_pct": rar_action_pct,
            "feedback_count": total_fb,
            "helpful_count": helpful_fb,
            "rar_feedback_pct": rar_feedback_pct,
            "status": "monitored"
        }
