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


def _safe_heartbeat(client: CoreClient, worker_id: str, info: dict[str, Any]) -> None:
    try:
        client.heartbeat(worker_id, info).raise_for_status()
    except Exception:
        logger.exception("Heartbeat failed")


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
    _safe_heartbeat(
        client,
        settings.worker_id,
        {
            "action": "startup",
            "mode": "poll",
            "component": "contract_worker",
        },
    )
    backoff_values = [5, 10, 30, 60]
    backoff_index = 0

    while True:
        if stop_event.is_set() and not in_progress.is_set():
            logger.info("Shutdown requested and no active job, exiting")
            break

        try:
            _safe_heartbeat(client, settings.worker_id, {"mode": "poll"})
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
            _safe_heartbeat(
                client,
                settings.worker_id,
                {
                    "action": "job_claimed",
                    "mode": "poll",
                    "job_id": str(job.get("id") or ""),
                },
            )

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_process_job, job)
                result_payload = None
                start_monotonic = time.monotonic()
                last_touch_monotonic = start_monotonic
                timed_out = False
                touch_interval = max(5, settings.job_touch_interval_seconds)
                while True:
                    elapsed = time.monotonic() - start_monotonic
                    remaining = settings.job_timeout_seconds - elapsed
                    if remaining <= 0:
                        timed_out = True
                        break
                    try:
                        result_payload = future.result(timeout=min(5.0, remaining))
                        break
                    except concurrent.futures.TimeoutError:
                        now_monotonic = time.monotonic()
                        if now_monotonic - last_touch_monotonic < touch_interval:
                            continue
                        last_touch_monotonic = now_monotonic
                        try:
                            touch = client.touch_job(
                                str(job["id"]),
                                settings.worker_id,
                                note="processing",
                            )
                            touch.raise_for_status()
                            _safe_heartbeat(
                                client,
                                settings.worker_id,
                                {
                                    "action": "job_touch",
                                    "mode": "poll",
                                    "job_id": str(job.get("id") or ""),
                                },
                            )
                        except Exception:
                            logger.exception("Job touch failed", extra={"job_id": job.get("id")})

                if timed_out:
                    client.mark_failed(job["id"], "execution timeout")
                    logger.error("Job timeout", extra={"job_id": job["id"]})
                    _safe_heartbeat(
                        client,
                        settings.worker_id,
                        {
                            "action": "job_failed",
                            "mode": "poll",
                            "job_id": str(job.get("id") or ""),
                            "error": "execution timeout",
                        },
                    )
                    in_progress.clear()
                    continue
                assert result_payload is not None

            response = client.submit_result(job["id"], result_payload)
            response.raise_for_status()
            logger.info("Job completed", extra={"job_id": job["id"]})
            _safe_heartbeat(
                client,
                settings.worker_id,
                {
                    "action": "job_completed",
                    "mode": "poll",
                    "job_id": str(job.get("id") or ""),
                },
            )
        except Exception as exc:
            logger.exception("Job processing failed")
            try:
                if "job" in locals() and isinstance(job, dict) and job.get("id"):
                    client.mark_failed(job["id"], str(exc))
                    _safe_heartbeat(
                        client,
                        settings.worker_id,
                        {
                            "action": "job_failed",
                            "mode": "poll",
                            "job_id": str(job.get("id") or ""),
                            "error": str(exc)[:400],
                        },
                    )
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
