from app.core.database import PostgresAppSession
from app.models.rules import RuleConfigProfile
db = PostgresAppSession()
profiles = db.query(RuleConfigProfile).all()
print("Profiles:", [p.version_tag for p in profiles])
for p in profiles:
    if p.version_tag == "system-default-v2":
        db.delete(p)
db.commit()
print("Deleted system-default-v2. Re-seeding...")
