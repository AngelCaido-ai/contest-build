import sys
from pathlib import Path

from redis import Redis
from rq import Queue, Worker

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings


def main() -> None:
    redis_conn = Redis.from_url(settings.redis_url)
    queue = Queue(connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)
    worker.work()


if __name__ == "__main__":
    main()
