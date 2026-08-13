import sys
import asyncio
sys.path.append('.')

from app.core.database import PostgresAppSession
from app.models.result import CVResult
from app.services.hiring_risk_analyzer import HiringRiskAnalyzer
from app.schemas.match import JobMatchResult
import json

async def run():
    with PostgresAppSession() as session:
        results = session.query(CVResult).filter(CVResult.status == 'COMPLETED').all()
        for res in results:
            if not isinstance(res.raw_data, dict):
                continue
            match_analysis = res.raw_data.get('match_analysis', {})
            best_match_data = match_analysis.get('best_match')
            
            modified = False
            
            if best_match_data:
                try:
                    best_match = JobMatchResult(**best_match_data)
                    HiringRiskAnalyzer.generate_risks(best_match, None, None)
                    match_analysis['best_match'] = best_match.model_dump(exclude_none=True)
                    modified = True
                    print(f"Updated best_match for {res.cv_key}")
                except Exception as e:
                    print(f"Error processing best_match for {res.cv_key}: {e}")
            
            suitable_openings_data = match_analysis.get('suitable_openings', [])
            if suitable_openings_data:
                new_openings = []
                for op_data in suitable_openings_data:
                    try:
                        op = JobMatchResult(**op_data)
                        HiringRiskAnalyzer.generate_risks(op, None, None)
                        new_openings.append(op.model_dump(exclude_none=True))
                        modified = True
                    except Exception as e:
                        print(f"Error processing opening for {res.cv_key}: {e}")
                        new_openings.append(op_data)
                match_analysis['suitable_openings'] = new_openings
                print(f"Updated suitable_openings for {res.cv_key}")
                
            if modified:
                res.raw_data['match_analysis'] = match_analysis
                # Force SQLAlchemy JSON mutation tracking
                res.raw_data = dict(res.raw_data)
                session.commit()
                print(f"Saved {res.cv_key}")

if __name__ == '__main__':
    asyncio.run(run())
