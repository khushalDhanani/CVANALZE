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
    results = asyncio.run(scan_uploads_directory("uploads"))
    skipped_count = sum(1 for r in results if r.get("match_analysis", {}).get("llm_skipped", False))
    skipped_pct = int((skipped_count / len(results)) * 100) if results else 0
    print(f"✨ Batch scanning finished. Successfully processed {len(results)} file(s). LLM Skipped: {skipped_count}/{len(results)} ({skipped_pct}%)")
