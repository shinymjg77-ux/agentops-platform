import asyncio
import logging
import os
import sys
from pathlib import Path
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

API_DIR = Path(__file__).resolve().parents[2] / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.delivery.scheduler import process_due_deliveries


def run() -> None:
    interval = int(os.getenv("WORKER_POLL_INTERVAL_SEC", "5"))
    logging.info("worker started, poll interval=%s sec", interval)

    while True:
        summary = asyncio.run(process_due_deliveries(force_process=False, limit=50))
        logging.info(
            "worker cycle processed=%s sent=%s retrying=%s failed=%s",
            summary["processed"],
            summary["sent"],
            summary["retrying"],
            summary["failed"],
        )
        time.sleep(interval)


if __name__ == "__main__":
    run()
