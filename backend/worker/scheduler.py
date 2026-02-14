import logging
import sys
import time
from pathlib import Path
from typing import Callable

sys.path.append(str(Path(__file__).resolve().parents[1]))

from rq.exceptions import NoSuchJobError
from rq.job import Job

from app.queue import queue, redis_conn
from app.tasks.deal_tasks import (
    check_deleted_posts,
    check_payment_timeouts,
    check_verification_windows,
    process_scheduled_posts,
    scan_escrow_deposits,
    sweep_completed_deposits,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TASK_TIMEOUTS: dict[Callable, int] = {
    scan_escrow_deposits: 120,
    check_verification_windows: 120,
    sweep_completed_deposits: 120,
    process_scheduled_posts: 60,
    check_deleted_posts: 60,
    check_payment_timeouts: 30,
}

TASKS = list(TASK_TIMEOUTS.keys())

ACTIVE_STATUSES = {"queued", "started", "scheduled"}


def _is_job_active(job_id: str) -> bool:
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        status = job.get_status()
        if status in ACTIVE_STATUSES:
            logger.debug("skip %s: already %s", job_id, status)
            return True
    except NoSuchJobError:
        pass
    return False


def main() -> None:
    logger.info("scheduler started, %d tasks every 20s", len(TASKS))
    while True:
        for task in TASKS:
            job_id = task.__name__
            try:
                if _is_job_active(job_id):
                    continue
                queue.enqueue(
                    task,
                    job_id=job_id,
                    job_timeout=TASK_TIMEOUTS[task],
                    result_ttl=0,
                )
            except Exception:
                logger.debug("skip enqueue %s (duplicate or error)", job_id)
        time.sleep(20)


if __name__ == "__main__":
    main()
