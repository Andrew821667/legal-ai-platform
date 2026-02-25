from __future__ import annotations

import concurrent.futures
import logging
import signal
import threading
import time
from typing import Any

from contract_worker.analyzer import analyze_contract
from contract_worker.core_client import CoreClient
from contract_worker.logging_config import setup_logging
from contract_worker.settings import settings

setup_logging()
logger = logging.getLogger(__name__)

stop_event = threading.Event()
in_progress = threading.Event()


def _handle_signal(signum: int, frame: Any) -> None:
    _ = frame
    logger.info("Signal received", extra={"signum": signum})
    stop_event.set()


def _process_job(job: dict) -> dict:
    text = job.get("document_text") or ""
    result = analyze_contract(text)
    return {
        "result_summary": result["summary"],
        "result_json": result,
        "report_url": None,
    }


def main() -> int:
    if not settings.api_key_worker:
        logger.error("API_KEY_WORKER is required")
        return 1

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    client = CoreClient(settings.core_api_url, settings.api_key_worker)
    backoff_values = [5, 10, 30, 60]
    backoff_index = 0

    while True:
        if stop_event.is_set() and not in_progress.is_set():
            logger.info("Shutdown requested and no active job, exiting")
            break

        try:
            client.heartbeat(settings.worker_id, {"mode": "poll"}).raise_for_status()
        except Exception:
            logger.exception("Heartbeat failed")

        try:
            claim = client.claim_job(settings.worker_id)
            if claim.status_code == 204:
                sleep_seconds = backoff_values[backoff_index]
                backoff_index = min(backoff_index + 1, len(backoff_values) - 1)
                logger.info("No jobs, backing off", extra={"sleep_seconds": sleep_seconds})
                time.sleep(sleep_seconds)
                continue

            claim.raise_for_status()
            job = claim.json()
            backoff_index = 0
            in_progress.set()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_process_job, job)
                try:
                    result_payload = future.result(timeout=settings.job_timeout_seconds)
                except concurrent.futures.TimeoutError:
                    client.mark_failed(job["id"], "execution timeout")
                    logger.error("Job timeout", extra={"job_id": job["id"]})
                    in_progress.clear()
                    continue

            response = client.submit_result(job["id"], result_payload)
            response.raise_for_status()
            logger.info("Job completed", extra={"job_id": job["id"]})
        except Exception as exc:
            logger.exception("Job processing failed")
            try:
                if "job" in locals() and isinstance(job, dict) and job.get("id"):
                    client.mark_failed(job["id"], str(exc))
            except Exception:
                logger.exception("Failed to mark job failed")
        finally:
            in_progress.clear()

        if stop_event.is_set():
            logger.info("Shutdown requested after finishing current job")
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
