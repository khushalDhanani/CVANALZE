from rq import Worker, Queue
from redis import Redis

def my_handler(job, exc_type, exc_value, traceback):
    print("MY HANDLER CALLED:", job.id, exc_value)
    return True

conn = Redis.from_url("redis://localhost:6379/0")
w = Worker([Queue('cv-processing', connection=conn)], connection=conn, exception_handlers=[my_handler])
print("Exception handlers:", w._exc_handlers)
