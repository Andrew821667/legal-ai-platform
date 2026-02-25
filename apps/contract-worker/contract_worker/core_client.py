from __future__ import annotations

from typing import Any

import requests


class CoreClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    def heartbeat(self, worker_id: str, info: dict[str, Any] | None = None) -> requests.Response:
        return requests.post(
            f"{self.base_url}/api/v1/workers/heartbeat",
            json={"worker_id": worker_id, "info": info or {}},
            headers=self.headers,
            timeout=self.timeout,
        )

    def claim_job(self, worker_id: str) -> requests.Response:
        return requests.post(
            f"{self.base_url}/api/v1/contract-jobs/claim",
            json={"worker_id": worker_id},
            headers=self.headers,
            timeout=self.timeout,
        )

    def submit_result(self, job_id: str, payload: dict[str, Any]) -> requests.Response:
        return requests.post(
            f"{self.base_url}/api/v1/contract-jobs/{job_id}/result",
            json=payload,
            headers=self.headers,
            timeout=self.timeout,
        )

    def mark_failed(self, job_id: str, error_text: str) -> requests.Response:
        return requests.patch(
            f"{self.base_url}/api/v1/contract-jobs/{job_id}",
            json={"status": "failed", "last_error": error_text[:500]},
            headers=self.headers,
            timeout=self.timeout,
        )
