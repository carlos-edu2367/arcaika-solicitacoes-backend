import redis
import logging
# 1. Removemos o 'Connection' da importação
from rq import Worker, Queue

from infra.config import Settings

logging.basicConfig(level=logging.INFO)

listen = ["upload_anexos"]

redis_conn = redis.from_url(Settings.REDIS_URL)

if __name__ == "__main__":
    
    # 2. Passamos a conexão diretamente para a Queue
    queues = [Queue(name, connection=redis_conn) for name in listen]

    # 3. Passamos a conexão diretamente para o Worker
    worker = Worker(queues, connection=redis_conn)

    worker.work(
        with_scheduler=True,
        logging_level="INFO"
    )