import sys
sys.path.append('.')
from app.core.database import PostgresAppSession
from app.models.result import CVResult

cv_key = "cv_1764688095_CandidateCVFileName_13349"
with PostgresAppSession() as session:
    obj = session.query(CVResult).filter(CVResult.cv_key == cv_key).first()
    if obj:
        print("Found", obj.status)
        obj.status = "FAILED"
        if isinstance(obj.raw_data, dict):
            obj.raw_data["status"] = "FAILED"
        session.commit()
        print("Updated")
    else:
        print("Not found")
