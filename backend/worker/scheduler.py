import logging
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.queue import queue
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

TASKS = [
    check_payment_timeouts,
    scan_escrow_deposits,
    process_scheduled_posts,
    check_deleted_posts,
    check_verification_windows,
    sweep_completed_deposits,
]


def main() -> None:
    logger.info("scheduler started, %d tasks every 20s", len(TASKS))
    while True:
        for task in TASKS:
            try:
                queue.enqueue(task)
            except Exception:
                logger.exception("failed to enqueue %s", task.__name__)
        time.sleep(20)


if __name__ == "__main__":
    main()
