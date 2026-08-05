from datetime import UTC, datetime
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.core.database import Base


class HRFeedback(Base):
    __tablename__ = "hr_feedback"
    __table_args__ = {"schema": "cvai"}

    feedback_id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String(100), nullable=False, index=True)
    candidate_id = Column(String(100), nullable=True)
    vacancy_id = Column(String(100), nullable=True)
    feedback_payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
