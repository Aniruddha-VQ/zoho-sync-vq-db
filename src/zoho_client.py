import logging
import time
from datetime import datetime
from typing import Any

import requests

from src.config import Settings
from src.time_utils import to_zoho_if_modified_since


class ZohoClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._access_token = ""
        self._token_expires_at = 0.0
        self._session = requests.Session()

    def _ensure_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at - 60:
            return self._access_token

        resp = self._session.post(
            f"{self._settings.zoho_accounts_base_url}/oauth/v2/token",
            params={
                "refresh_token": self._settings.zoho_refresh_token,
                "client_id": self._settings.zoho_client_id,
                "client_secret": self._settings.zoho_client_secret,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()

        token = payload.get("access_token", "")
        if not token:
            raise RuntimeError(f"Unable to fetch Zoho access token: {payload}")

        expires_in = int(payload.get("expires_in", 3600))
        self._access_token = token
        self._token_expires_at = now + expires_in
        return self._access_token

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        token = self._ensure_token()
        request_headers = {
            "Authorization": f"Zoho-oauthtoken {token}",
        }
        if headers:
            request_headers.update(headers)

        url = f"{self._settings.zoho_base_url}{path}"
        for attempt in range(3):
            resp = self._session.request(
                method=method,
                url=url,
                params=params,
                headers=request_headers,
                timeout=60,
            )
            if resp.status_code in (429, 500, 502, 503, 504):
                wait_seconds = 2**attempt
                logging.warning(
                    "Zoho request failed with status %s. Retrying in %s sec.",
                    resp.status_code,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue
            return resp

        return resp

    def get_records(
        self, module_api_name: str, modified_since: datetime | None = None
    ) -> list[dict[str, Any]]:
        page = 1
        all_rows: list[dict[str, Any]] = []
        headers: dict[str, str] = {}
        if modified_since:
            headers["If-Modified-Since"] = to_zoho_if_modified_since(modified_since)

        while True:
            resp = self._request(
                "GET",
                f"/crm/v2/{module_api_name}",
                params={"page": page, "per_page": 200},
                headers=headers,
            )

            if resp.status_code == 304:
                break
            if resp.status_code == 204:
                break
            resp.raise_for_status()

            payload = resp.json()
            rows = payload.get("data", [])
            all_rows.extend(rows)

            more_records = (
                payload.get("info", {}).get("more_records", False)
                if isinstance(payload, dict)
                else False
            )
            if not more_records:
                break
            page += 1

        return all_rows

    def get_users(self) -> list[dict[str, Any]]:
        page = 1
        rows: list[dict[str, Any]] = []
        while True:
            resp = self._request(
                "GET",
                "/crm/v2/users",
                params={"type": "AllUsers", "page": page, "per_page": 200},
            )
            if resp.status_code == 204:
                break
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("users", []) if isinstance(payload, dict) else []
            rows.extend(data)
            more_records = (
                payload.get("info", {}).get("more_records", False)
                if isinstance(payload, dict)
                else False
            )
            if not more_records:
                break
            page += 1
        return rows
