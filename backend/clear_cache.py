from app.core.cache import config_cache_manager
from app.core.cache import _REDIS_CLIENT
if _REDIS_CLIENT:
    _REDIS_CLIENT.flushall()
else:
    print("No redis client!")
