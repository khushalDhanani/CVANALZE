from app.core.config import settings
from app.main import app
from app.services.cv_service import scan_uploads_directory

__all__ = ["app"]


import asyncio
import warnings

# Suppress harmless leaked semaphore warnings from docling/pytorch
warnings.filterwarnings("ignore", category=UserWarning, module="multiprocessing.resource_tracker")

if __name__ == "__main__":
    from app.core.database import init_db

    init_db()

    # Warm cache synchronously before the batch scan (CLI mode)
    try:
        from app.services.cache_warmer import warm_all

        warm_all()
    except Exception as exc:
        print(f"[WARMUP] CLI cache warmup skipped: {exc}")

    print("🚀 Starting Resource-Optimized Batch CV Scanner for 'uploads/' directory...")
    print(
        f"⚙️ Settings: Batch Size={settings.BATCH_SIZE} | "
        f"Workers={settings.MAX_CONCURRENT_WORKERS} | "
        f"Throttle Delay={settings.THROTTLE_DELAY_SECONDS}s | "
        f"Timeout={settings.EXTRACTION_TIMEOUT_SECONDS}s\n"
    )
    submissions = asyncio.run(scan_uploads_directory("uploads"))
    print(f"📦 Queued {len(submissions)} CV file(s). Use the status API to monitor completion.")
