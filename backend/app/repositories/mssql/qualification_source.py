from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.mssql.taxonomy import QualificationMst

class QualificationSourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_qualifications(self) -> list[QualificationMst]:
        return self.db.scalars(select(QualificationMst)).all()
