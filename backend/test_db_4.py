import asyncio
from sqlalchemy import text
from app.core.database import PostgresAppSession

async def main():
    try:
        session = PostgresAppSession()
        stmt = text('SELECT COUNT(*) FROM "DepartmentDomainMaster"')
        result = session.execute(stmt).scalar()
        print("DOMAINS COUNT:", result)
    except Exception as e:
        print("ERROR:", e)
    
if __name__ == "__main__":
    asyncio.run(main())
