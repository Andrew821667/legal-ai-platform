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

    def list_posts(
        self,
        limit: int = 20,
        status: str | None = None,
        newest_first: bool = False,
    ) -> requests.Response:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if newest_first:
            params["newest_first"] = True
        return requests.get(
            f"{self.base_url}/api/v1/scheduled-posts",
            params=params,
            headers=self.headers,
            timeout=self.timeout,
        )

    def list_automation_controls(self, scope: str | None = None) -> requests.Response:
        params: dict[str, Any] = {}
        if scope:
            params["scope"] = scope
        return requests.get(
            f"{self.base_url}/api/v1/automation-controls",
            params=params,
            headers=self.headers,
            timeout=self.timeout,
        )

    def update_automation_control(self, key: str, payload: dict[str, Any]) -> requests.Response:
        return requests.put(
            f"{self.base_url}/api/v1/automation-controls/{key}",
            json=payload,
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

    def get_post(self, post_id: str) -> requests.Response:
        return requests.get(
            f"{self.base_url}/api/v1/scheduled-posts/{post_id}",
            headers=self.headers,
            timeout=self.timeout,
        )

    def delete_post(self, post_id: str) -> requests.Response:
        return requests.delete(
            f"{self.base_url}/api/v1/scheduled-posts/{post_id}",
            headers=self.headers,
            timeout=self.timeout,
        )

    def lookup_post_by_telegram_message(
        self,
        message_id: int,
        *,
        channel_id: str | None = None,
        channel_username: str | None = None,
    ) -> requests.Response:
        params: dict[str, Any] = {"message_id": message_id}
        if channel_id:
            params["channel_id"] = channel_id
        if channel_username:
            params["channel_username"] = channel_username
        return requests.get(
            f"{self.base_url}/api/v1/scheduled-posts/lookup/by-telegram-message",
            params=params,
            headers=self.headers,
            timeout=self.timeout,
        )

    def create_post_feedback(self, post_id: str, payload: dict[str, Any]) -> requests.Response:
        return requests.post(
            f"{self.base_url}/api/v1/scheduled-posts/{post_id}/feedback",
            json=payload,
            headers=self.headers,
            timeout=self.timeout,
        )

    def list_post_feedback(self, post_id: str, limit: int = 20) -> requests.Response:
        return requests.get(
            f"{self.base_url}/api/v1/scheduled-posts/{post_id}/feedback",
            params={"limit": limit},
            headers=self.headers,
            timeout=self.timeout,
        )

    def workers_status(self) -> requests.Response:
        return requests.get(
            f"{self.base_url}/api/v1/workers/status",
            headers=self.headers,
            timeout=self.timeout,
        )

    def workers_activity(self, worker_id: str, *, hours: int = 24, limit: int = 30) -> requests.Response:
        return requests.get(
            f"{self.base_url}/api/v1/workers/{worker_id}/activity",
            params={"hours": hours, "limit": limit},
            headers=self.headers,
            timeout=self.timeout,
        )

    def worker_heartbeat(self, worker_id: str, info: dict[str, Any] | None = None) -> requests.Response:
        return requests.post(
            f"{self.base_url}/api/v1/workers/heartbeat",
            json={"worker_id": worker_id, "info": info or {}},
            headers=self.headers,
            timeout=self.timeout,
        )

    def reset_stale_scheduled_posts(self, older_than_minutes: int = 30) -> requests.Response:
        return requests.post(
            f"{self.base_url}/api/v1/scheduled-posts/reset-stale?older_than_minutes={older_than_minutes}",
            headers=self.headers,
            timeout=self.timeout,
        )

    def reset_stale_contract_jobs(self, older_than_minutes: int = 30) -> requests.Response:
        return requests.post(
            f"{self.base_url}/api/v1/contract-jobs/reset-stale?older_than_minutes={older_than_minutes}",
            headers=self.headers,
            timeout=self.timeout,
        )
