import sys
import asyncio
sys.path.append('.')

from app.core.database import PostgresAppSession
from app.models.result import CVResult

with PostgresAppSession() as session:
    res = session.query(CVResult).filter(CVResult.cv_key == "cv_1764688095_CandidateCVFileName_13349").first()
    if res:
        res.status = 'COMPLETED'
        if isinstance(res.raw_data, dict):
            res.raw_data['status'] = 'COMPLETED'
            res.raw_data = dict(res.raw_data)
        session.commit()
        print("Fixed status for cv_1764688095_CandidateCVFileName_13349")
