from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx

from ._version import __version__
from .exceptions import (
    CrenoAPIError,
    CrenoAuthenticationError,
    CrenoConflictError,
    CrenoError,
    CrenoForbiddenError,
    CrenoNotFoundError,
    CrenoPlanLimitError,
    CrenoRateLimitError,
    CrenoValidationError,
)
from .models import Availability, Booking, DateLike, DatetimeLike, ServiceType, to_date_str, to_iso

DEFAULT_BASE_URL = "https://api.crenoapp.com"
DEFAULT_TIMEOUT = 10.0

# Only applied to the two read-only GET endpoints, never to create_booking
# (see its docstring for why).
_MAX_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 0.2


def _drop_none(values: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


class CrenoClient:
    """Synchronous client for Creno's public scheduling and booking API.

    The API key you pass here is the same "publishable" key used by Creno's
    browser widgets. In the browser, safety comes from Creno's origin
    allowlist, not from keeping the key secret. This client makes
    server-to-server calls with no Origin header, so that allowlist check
    never applies here, treat the key as sensitive in your own backend.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={
                "X-API-Key": api_key,
                "User-Agent": f"creno-python/{__version__}",
                "X-Client-Library": "python",
                "Content-Type": "application/json",
            },
            transport=transport,
        )

    def __enter__(self) -> "CrenoClient":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # -- endpoints -----------------------------------------------------------

    def list_service_types(self, *, resource_id: Optional[str] = None) -> List[ServiceType]:
        """GET /v1/public/service-types. Retries on network errors or 5xx."""
        params = _drop_none({"resourceId": resource_id})
        rows = self._request_idempotent("GET", "/v1/public/service-types", params=params)
        return [ServiceType._from_api(row) for row in rows]

    def get_availability(
        self,
        *,
        from_: DateLike,
        to: DateLike,
        resource_id: Optional[str] = None,
        service_type_id: Optional[str] = None,
    ) -> Availability:
        """GET /v1/public/availability. Retries on network errors or 5xx."""
        params = _drop_none(
            {
                "from": to_date_str(from_),
                "to": to_date_str(to),
                "resourceId": resource_id,
                "serviceTypeId": service_type_id,
            }
        )
        data = self._request_idempotent("GET", "/v1/public/availability", params=params)
        return Availability._from_api(data)

    def create_booking(
        self,
        *,
        start_at: DatetimeLike,
        customer_name: str,
        customer_email: str,
        resource_id: Optional[str] = None,
        service_type_id: Optional[str] = None,
        customer_phone: Optional[str] = None,
        notes: Optional[str] = None,
        lang: Optional[str] = None,
        turnstile_token: Optional[str] = None,
    ) -> Booking:
        """POST /v1/public/bookings.

        Never retried automatically: a lost response after the booking was
        actually created server-side, followed by a client-side retry, could
        still submit a second real booking attempt to a real customer, even
        though Creno's own database can never double-book the same slot.
        """
        body = _drop_none(
            {
                "resourceId": resource_id,
                "serviceTypeId": service_type_id,
                "startAt": to_iso(start_at),
                "customerName": customer_name,
                "customerEmail": customer_email,
                "customerPhone": customer_phone,
                "notes": notes,
                "lang": lang,
                "turnstileToken": turnstile_token,
            }
        )
        data = self._request("POST", "/v1/public/bookings", json=body)
        return Booking._from_api(data)

    # -- internals -------------------------------------------------------------

    def _request_idempotent(self, method: str, path: str, *, params: Dict[str, Any]) -> Any:
        last_error: Optional[CrenoError] = None
        for attempt in range(_MAX_RETRY_ATTEMPTS):
            try:
                return self._request(method, path, params=params)
            except CrenoError as exc:
                retryable = exc.status_code is None or exc.status_code >= 500
                if not retryable or attempt == _MAX_RETRY_ATTEMPTS - 1:
                    raise
                last_error = exc
                time.sleep(_RETRY_BASE_DELAY_SECONDS * (2**attempt))
        assert last_error is not None  # pragma: no cover - loop always raises or returns
        raise last_error

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        try:
            response = self._client.request(method, path, params=params, json=json)
        except httpx.TransportError as exc:
            raise CrenoAPIError(f"Network error calling the Creno API: {exc}") from exc

        if response.status_code // 100 == 2:
            if response.status_code == 204 or not response.content:
                return None
            return response.json()

        try:
            body: Any = response.json()
        except ValueError:
            body = None
        message = (body or {}).get("error") if isinstance(body, dict) else None
        message = message or response.text or response.reason_phrase

        if response.status_code == 401:
            raise CrenoAuthenticationError(message, status_code=401, response_body=body)
        if response.status_code == 403:
            raise CrenoForbiddenError(message, status_code=403, response_body=body)
        if response.status_code == 404:
            raise CrenoNotFoundError(message, status_code=404, response_body=body)
        if response.status_code == 400:
            raise CrenoValidationError(message, status_code=400, response_body=body)
        if response.status_code == 409:
            raise CrenoConflictError(message, status_code=409, response_body=body)
        if response.status_code == 402:
            raise CrenoPlanLimitError(
                message,
                status_code=402,
                response_body=body,
                limit_type=(body or {}).get("limitType") if isinstance(body, dict) else None,
                plan=(body or {}).get("plan") if isinstance(body, dict) else None,
            )
        if response.status_code == 429:
            raise CrenoRateLimitError(message, status_code=429, response_body=body)
        raise CrenoAPIError(message, status_code=response.status_code, response_body=body)
