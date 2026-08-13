from app.core.cache import cv_result_cache_manager
cv_result_cache_manager.redis.flushdb()
print("Flushed")
