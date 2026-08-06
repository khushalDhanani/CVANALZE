import asyncio
from app.core.database import db
from sqlalchemy import text

async def main():
    domains = await db.fetch_all(text("SELECT * FROM department_domains"))
    print("DOMAINS:", len(domains))
    
if __name__ == "__main__":
    asyncio.run(main())
