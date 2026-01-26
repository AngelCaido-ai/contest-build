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
)


def main() -> None:
    while True:
        queue.enqueue(check_payment_timeouts)
        queue.enqueue(process_scheduled_posts)
        queue.enqueue(check_deleted_posts)
        queue.enqueue(check_verification_windows)
        time.sleep(60)


if __name__ == "__main__":
    main()
