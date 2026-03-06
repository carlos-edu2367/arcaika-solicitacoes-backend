import redis
from rq import Queue
from infra.config import Settings

redis_conn = redis.from_url(
    Settings.REDIS_URL
)

fila_upload = Queue(
    "upload_anexos",
    connection=redis_conn
)