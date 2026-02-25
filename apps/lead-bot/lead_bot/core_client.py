from __future__ import annotations

import requests


class CoreClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    def post_lead(self, payload: dict, idempotency_key: str | None = None) -> requests.Response:
        headers = dict(self._headers)
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return requests.post(
            f"{self.base_url}/api/v1/leads",
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )

    def post_event(self, payload: dict, idempotency_key: str | None = None) -> requests.Response:
        headers = dict(self._headers)
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return requests.post(
            f"{self.base_url}/api/v1/events",
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
