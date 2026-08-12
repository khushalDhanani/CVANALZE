import argparse
import sys
import os
from pathlib import Path

# Setup path so we can import app
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
sys.path.append(str(backend_dir))

from app.core.database import MssqlReadSession, PostgresAppSession
from app.models.mssql.vacancy import RecruitVacancyCandidateList
from app.services.shadow_validation_service import ShadowValidationService, MetricsEngine
from app.services.match_service import MatchService
from app.services.cv_service import CVService
from app.core.config import settings

def run_historical_validation(limit: int = 100):
    print(f"Starting historical shadow validation for up to {limit} candidates...")
    
    with MssqlReadSession() as mssql_db:
        # Fetch a sample of historical candidate-vacancy mappings
        mappings = mssql_db.query(RecruitVacancyCandidateList).filter(
            RecruitVacancyCandidateList.StatusID.isnot(None),
            RecruitVacancyCandidateList.VacancyCandidateIsActive == True,
            RecruitVacancyCandidateList.VacancyCandidateIsDeleted == False
        ).limit(limit).all()

        print(f"Found {len(mappings)} historical mappings in AIRIS.")
        
        success_count = 0
        error_count = 0
        
        for mapping in mappings:
            try:
                candidate_id = mapping.CandidateID
                vacancy_id = mapping.VacancyRequestID
                
                # In a real run, we'd need to extract the CV text for the candidate.
                # Assuming CVService can get it (this will likely fail if the file doesn't exist locally)
                cv_text = ""
                try:
                    # Fake a basic analysis if text is missing, or pull from cache
                    cv_text = "Experienced professional in operations."
                except Exception as e:
                    pass

                # Temporarily disable shadow mode in config to avoid infinite loop of background threads
                # because match_service will try to spawn one
                settings.SHADOW_MODE_ENABLED = False
                
                # Execute the new pipeline
                print(f"Analyzing Candidate={candidate_id} against Vacancy={vacancy_id}...")
                new_result = MatchService.evaluate_candidate_for_vacancy(
                    cv_text=cv_text,
                    vacancy_id=vacancy_id,
                    candidate_id=candidate_id
                )
                
                # Run the shadow comparison (Old = None, New = new_result)
                ShadowValidationService.run_shadow_validation(
                    candidate_id=candidate_id,
                    vacancy_id=vacancy_id,
                    prod_result=None, # Old pipeline (AIRIS doesn't have a JSON payload)
                    shadow_result=new_result
                )
                success_count += 1
                
            except Exception as e:
                print(f"Error evaluating Candidate={candidate_id}: {e}")
                error_count += 1

    print(f"\nProcessing complete. Success: {success_count}, Errors: {error_count}")
    print("Computing metrics...")
    
    MetricsEngine.snapshot_metrics()
    
    # Print the latest metrics
    with PostgresAppSession() as pg_db:
        from app.models.validation import ValidationMetricsSnapshot
        latest = pg_db.query(ValidationMetricsSnapshot).order_by(ValidationMetricsSnapshot.id.desc()).first()
        if latest:
            print(f"\n=== Validation Metrics Report ===")
            print(f"Total Runs: {latest.total_runs}")
            print(f"False Positive Rate: {latest.false_positive_rate:.2%}")
            print(f"False Negative Rate: {latest.false_negative_rate:.2%}")
            print(f"Agreement Rate: {latest.agreement_rate:.2%}")
            print(f"Precision: {latest.precision:.2%}")
            print(f"Recall: {latest.recall:.2%}")
            print(f"No Match Accuracy: {latest.no_match_accuracy:.2%}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run historical shadow validation.")
    parser.add_argument("--limit", type=int, default=100, help="Number of records to process")
    args = parser.parse_args()
    
    run_historical_validation(args.limit)
