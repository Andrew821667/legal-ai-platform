from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter


class CoreClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=50)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> requests.Response:
        return self.session.request(
            method=method.upper(),
            url=f"{self.base_url}{path}",
            params=params,
            json=json,
            headers=self.headers,
            timeout=self.timeout,
        )

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "CoreClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def create_scheduled_post(self, payload: dict[str, Any]) -> requests.Response:
        return self._request("POST", "/api/v1/scheduled-posts", json=payload)

    def claim_posts(self, limit: int) -> requests.Response:
        return self._request("POST", "/api/v1/scheduled-posts/claim", params={"limit": limit})

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
        return self._request("GET", "/api/v1/scheduled-posts", params=params)

    def list_automation_controls(self, scope: str | None = None) -> requests.Response:
        params: dict[str, Any] = {}
        if scope:
            params["scope"] = scope
        return self._request("GET", "/api/v1/automation-controls", params=params)

    def update_automation_control(self, key: str, payload: dict[str, Any]) -> requests.Response:
        return self._request("PUT", f"/api/v1/automation-controls/{key}", json=payload)

    def patch_post(self, post_id: str, payload: dict[str, Any]) -> requests.Response:
        return self._request("PATCH", f"/api/v1/scheduled-posts/{post_id}", json=payload)

    def get_post(self, post_id: str) -> requests.Response:
        return self._request("GET", f"/api/v1/scheduled-posts/{post_id}")

    def delete_post(self, post_id: str) -> requests.Response:
        return self._request("DELETE", f"/api/v1/scheduled-posts/{post_id}")

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
        return self._request(
            "GET",
            "/api/v1/scheduled-posts/lookup/by-telegram-message",
            params=params,
        )

    def create_post_feedback(self, post_id: str, payload: dict[str, Any]) -> requests.Response:
        return self._request("POST", f"/api/v1/scheduled-posts/{post_id}/feedback", json=payload)

    def list_post_feedback(self, post_id: str, limit: int = 20) -> requests.Response:
        return self._request(
            "GET",
            f"/api/v1/scheduled-posts/{post_id}/feedback",
            params={"limit": limit},
        )

    def workers_status(self) -> requests.Response:
        return self._request("GET", "/api/v1/workers/status")

    def workers_activity(self, worker_id: str, *, hours: int = 24, limit: int = 30) -> requests.Response:
        return self._request(
            "GET",
            f"/api/v1/workers/{worker_id}/activity",
            params={"hours": hours, "limit": limit},
        )

    def worker_heartbeat(self, worker_id: str, info: dict[str, Any] | None = None) -> requests.Response:
        return self._request(
            "POST",
            "/api/v1/workers/heartbeat",
            json={"worker_id": worker_id, "info": info or {}},
        )

    def reset_stale_scheduled_posts(self, older_than_minutes: int = 30) -> requests.Response:
        return self._request(
            "POST",
            "/api/v1/scheduled-posts/reset-stale",
            params={"older_than_minutes": older_than_minutes},
        )

    def reset_stale_contract_jobs(self, older_than_minutes: int = 30) -> requests.Response:
        return self._request(
            "POST",
            "/api/v1/contract-jobs/reset-stale",
            params={"older_than_minutes": older_than_minutes},
        )

    def reader_feedback_summary(self, days: int = 7) -> requests.Response:
        return self._request(
            "GET",
            "/api/v1/scheduled-posts/feedback/reader-summary",
            params={"days": days},
        )

    def reader_funnel_summary(self, days: int = 7) -> requests.Response:
        return self._request(
            "GET",
            "/api/v1/scheduled-posts/feedback/reader-funnel",
            params={"days": days},
        )

    def reader_miniapp_events_summary(self, *, hours: int = 24, limit_users: int = 10) -> requests.Response:
        return self._request(
            "GET",
            "/api/v1/reader/miniapp/events/summary",
            params={"hours": hours, "limit_users": limit_users},
        )
