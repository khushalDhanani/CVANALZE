import sys
import asyncio
sys.path.append('.')
from app.services.processing_queue import _process_source, ProcessingJobRepository
from app.core.database import PostgresAppSession
from app.models.result import CVResult
import json

cv_key = "cv_1764688095_CandidateCVFileName_13349"

async def run():
    job = ProcessingJobRepository.get_active(cv_key)
    if job:
        print("Found active job:", job.job_id)
        from app.services.upload_service import UploadService
        source = UploadService.load_reprocessable_upload(
            storage_filename=job.storage_filename,
            original_filename=job.filename,
            cv_key=job.cv_key,
        )
        if source:
            print("Source loaded. Processing...")
            res = await _process_source(
                record=job,
                filename=source.safe_filename,
                content=source.content,
                content_type=source.detected_content_type,
                storage_filename=source.storage_filename,
            )
            print("Processed:", res.get("status"))
        else:
            print("Source not found.")
    else:
        print("No active job found.")

if __name__ == "__main__":
    asyncio.run(run())
