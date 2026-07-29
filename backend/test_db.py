from app.core.database import SessionLocal
from app.services.vacancy_service import VacancyService
db = SessionLocal()
svc = VacancyService(db)
vacancies = svc.get_active_vacancies()
ids = [v.id for v in vacancies]
print("Total rows:", len(ids))
print("Unique rows:", len(set(ids)))
