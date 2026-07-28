import json

import httpx
import pytest

from creno import (
    CrenoAuthenticationError,
    CrenoConflictError,
    CrenoForbiddenError,
    CrenoNotFoundError,
    CrenoPlanLimitError,
    CrenoRateLimitError,
    CrenoValidationError,
)


def test_sends_api_key_header(client_with):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["api_key"] = request.headers["x-api-key"]
        return httpx.Response(200, json=[])

    client_with(handler).list_service_types()
    assert seen["api_key"] == "pk_test_123"


def test_list_service_types_parses_rows(client_with):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"id": "st1", "resourceId": "r1", "name": "Haircut", "active": True, "sortOrder": 0}],
        )

    result = client_with(handler).list_service_types()
    assert len(result) == 1
    assert result[0].name == "Haircut"
    assert result[0].sort_order == 0


def test_get_availability_parses_slots(client_with):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "resourceId": "r1",
                "timezone": "America/Toronto",
                "slots": [{"startAt": "2026-08-01T13:00:00Z", "endAt": "2026-08-01T13:30:00Z"}],
            },
        )

    availability = client_with(handler).get_availability(from_="2026-08-01", to="2026-08-07")
    assert availability.timezone == "America/Toronto"
    assert availability.slots[0].start_at.hour == 13


def test_get_availability_accepts_date_objects(client_with):
    from datetime import date

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["query"] = dict(request.url.params)
        return httpx.Response(200, json={"resourceId": "r1", "timezone": "UTC", "slots": []})

    client_with(handler).get_availability(from_=date(2026, 8, 1), to=date(2026, 8, 7))
    assert seen["query"]["from"] == "2026-08-01"
    assert seen["query"]["to"] == "2026-08-07"


def test_create_booking_omits_none_fields_from_body(client_with):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.read())
        return httpx.Response(
            201,
            json={
                "id": "b1",
                "tenantId": "t1",
                "resourceId": "r1",
                "serviceTypeId": None,
                "customerName": "Jane Doe",
                "customerEmail": "jane@example.com",
                "customerPhone": None,
                "startAt": "2026-08-01T13:00:00Z",
                "endAt": "2026-08-01T13:30:00Z",
                "status": "confirmed",
                "holdExpiresAt": None,
                "notes": None,
                "createdAt": "2026-08-01T12:00:00Z",
            },
        )

    booking = client_with(handler).create_booking(
        start_at="2026-08-01T13:00:00Z",
        customer_name="Jane Doe",
        customer_email="jane@example.com",
    )
    assert "resourceId" not in seen["body"]
    assert "serviceTypeId" not in seen["body"]
    assert "customerPhone" not in seen["body"]
    assert booking.status == "confirmed"
    assert booking.service_type_id is None


def test_create_booking_normalizes_aware_datetime_to_utc_iso(client_with):
    from datetime import datetime, timedelta, timezone

    seen = {}
    eastern = timezone(timedelta(hours=-4))

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.read())
        return httpx.Response(
            201,
            json={
                "id": "b1",
                "tenantId": "t1",
                "resourceId": "r1",
                "serviceTypeId": None,
                "customerName": "Jane Doe",
                "customerEmail": "jane@example.com",
                "customerPhone": None,
                "startAt": "2026-08-01T17:00:00Z",
                "endAt": "2026-08-01T17:30:00Z",
                "status": "confirmed",
                "holdExpiresAt": None,
                "notes": None,
                "createdAt": "2026-08-01T12:00:00Z",
            },
        )

    client_with(handler).create_booking(
        start_at=datetime(2026, 8, 1, 13, 0, 0, tzinfo=eastern),
        customer_name="Jane Doe",
        customer_email="jane@example.com",
    )
    assert seen["body"]["startAt"] == "2026-08-01T17:00:00Z"


def test_create_booking_rejects_naive_datetime(client_with):
    from datetime import datetime

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - should never be called
        return httpx.Response(201, json={})

    with pytest.raises(ValueError):
        client_with(handler).create_booking(
            start_at=datetime(2026, 8, 1, 13, 0, 0),
            customer_name="Jane Doe",
            customer_email="jane@example.com",
        )


@pytest.mark.parametrize(
    "status_code,exc_class",
    [
        (401, CrenoAuthenticationError),
        (403, CrenoForbiddenError),
        (404, CrenoNotFoundError),
        (400, CrenoValidationError),
        (409, CrenoConflictError),
        (429, CrenoRateLimitError),
    ],
)
def test_error_status_codes_map_to_exceptions(client_with, status_code, exc_class):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "boom"})

    with pytest.raises(exc_class) as exc_info:
        client_with(handler).list_service_types()
    assert exc_info.value.status_code == status_code
    assert exc_info.value.message == "boom"


def test_plan_limit_error_carries_limit_type_and_plan(client_with):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            402,
            json={"error": "Plan limit reached", "limitType": "bookingsPerMonth", "plan": "starter"},
        )

    with pytest.raises(CrenoPlanLimitError) as exc_info:
        client_with(handler).create_booking(
            start_at="2026-08-01T13:00:00Z", customer_name="Jane", customer_email="jane@example.com"
        )
    assert exc_info.value.limit_type == "bookingsPerMonth"
    assert exc_info.value.plan == "starter"


def test_get_availability_retries_on_500_then_succeeds(client_with):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 2:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json={"resourceId": "r1", "timezone": "UTC", "slots": []})

    result = client_with(handler).get_availability(from_="2026-08-01", to="2026-08-07")
    assert calls["count"] == 2
    assert result.timezone == "UTC"


def test_get_availability_does_not_retry_on_4xx(client_with):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(404, json={"error": "Resource not found"})

    with pytest.raises(CrenoNotFoundError):
        client_with(handler).get_availability(from_="2026-08-01", to="2026-08-07")
    assert calls["count"] == 1


def test_create_booking_does_not_retry_on_500(client_with):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(Exception):
        client_with(handler).create_booking(
            start_at="2026-08-01T13:00:00Z", customer_name="Jane", customer_email="jane@example.com"
        )
    assert calls["count"] == 1


def test_context_manager_closes_client(client_with):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = client_with(handler)
    with client:
        client.list_service_types()
    assert client._client.is_closed
