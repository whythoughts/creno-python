"""Real HTTP integration tests against a running Creno API instance.

Skipped unless CRENO_TEST_API_URL and CRENO_TEST_API_KEY are set, so a bare
`pytest` run never silently "passes" without ever touching the network.

    pnpm dev:api    # from the platform repo root, in one terminal
    CRENO_TEST_API_URL=http://localhost:3000 \\
    CRENO_TEST_API_KEY=<a real seeded tenant's publishable key> \\
    pytest tests/test_client_integration.py -m integration
"""

import os
import uuid
from datetime import date, timedelta

import pytest

from creno import CrenoClient

API_URL = os.environ.get("CRENO_TEST_API_URL")
API_KEY = os.environ.get("CRENO_TEST_API_KEY")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not API_URL or not API_KEY,
        reason=(
            "Set CRENO_TEST_API_URL and CRENO_TEST_API_KEY to run these tests against "
            "a real running Creno API instance."
        ),
    ),
]


@pytest.fixture
def client():
    with CrenoClient(api_key=API_KEY, base_url=API_URL) as c:
        yield c


def test_list_service_types_real(client: CrenoClient) -> None:
    result = client.list_service_types()
    assert isinstance(result, list)


def test_get_availability_real(client: CrenoClient) -> None:
    today = date.today()
    availability = client.get_availability(from_=today, to=today + timedelta(days=7))
    assert availability.timezone


def test_create_booking_real(client: CrenoClient) -> None:
    today = date.today()
    availability = client.get_availability(from_=today, to=today + timedelta(days=14))
    if not availability.slots:
        pytest.skip("No available slots in the next 14 days for the test tenant; seed more availability.")

    slot = availability.slots[0]
    booking = client.create_booking(
        start_at=slot.start_at,
        customer_name="Creno SDK Integration Test",
        customer_email=f"sdk-integration-test-{uuid.uuid4().hex[:8]}@example.com",
        notes="Created by the creno Python SDK's integration test suite.",
    )
    assert booking.status in ("pending", "confirmed")
    assert booking.start_at == slot.start_at
