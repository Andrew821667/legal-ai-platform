from __future__ import annotations

from typing import Any

import requests


class CoreClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    def create_scheduled_post(self, payload: dict[str, Any]) -> requests.Response:
        return requests.post(
            f"{self.base_url}/api/v1/scheduled-posts",
            json=payload,
            headers=self.headers,
            timeout=self.timeout,
        )

    def claim_posts(self, limit: int) -> requests.Response:
        return requests.post(
            f"{self.base_url}/api/v1/scheduled-posts/claim?limit={limit}",
            headers=self.headers,
            timeout=self.timeout,
        )

    def patch_post(self, post_id: str, payload: dict[str, Any]) -> requests.Response:
        return requests.patch(
            f"{self.base_url}/api/v1/scheduled-posts/{post_id}",
            json=payload,
            headers=self.headers,
            timeout=self.timeout,
        )
