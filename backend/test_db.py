import asyncio
from sqlalchemy import text
from app.core.database import SessionLocal

def run_query():
    with SessionLocal() as db:
        res = db.execute(text("SELECT TOP 5 * FROM CandidateCV WHERE CVID = 'ut1765894215' OR CandidateID = 'ut1765894215'")).mappings().all()
        for r in res:
            print(r.get('CVID'), r.get('CandidateID'))

if __name__ == "__main__":
    run_query()
