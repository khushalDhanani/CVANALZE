from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.mssql.taxonomy import (
    RecruitDomainKnowledgeMst,
    RecruitDomainKnowledgeDeptDet,
    RecruitDomainKnowledgeSkillDet,
    RecruitSkillMst,
    RecruitSkillTypeMst,
    TransactionStatusMst
)

class TaxonomySourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active_domains(self) -> list[RecruitDomainKnowledgeMst]:
        return self.db.scalars(
            select(RecruitDomainKnowledgeMst).where(RecruitDomainKnowledgeMst.IsActive == True)
        ).all()

    def get_active_skills(self) -> list[RecruitSkillMst]:
        return self.db.scalars(
            select(RecruitSkillMst).where(RecruitSkillMst.IsActive == True)
        ).all()
