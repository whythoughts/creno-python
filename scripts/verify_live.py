#!/usr/bin/env python3
"""Runs real requests against a live Creno API instance and prints the results.

This is the standalone, human-runnable proof that the SDK actually works end
to end, separate from the mocked/gated test suites in tests/.

Usage:
    pnpm dev:api   # from the platform repo root, in one terminal

    CRENO_API_URL=http://localhost:3000 \\
    CRENO_API_KEY=<a real seeded tenant's publishable key> \\
    python scripts/verify_live.py
"""

import os
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from creno import CrenoClient, CrenoError  # noqa: E402


def main() -> int:
    api_url = os.environ.get("CRENO_API_URL", "http://localhost:3000")
    api_key = os.environ.get("CRENO_API_KEY")
    if not api_key:
        print("Set CRENO_API_KEY to a real tenant's publishable key before running this script.")
        return 1

    with CrenoClient(api_key=api_key, base_url=api_url) as client:
        print(f"Connecting to {api_url} ...")

        service_types = client.list_service_types()
        print(f"Service types: {len(service_types)} found")
        for service_type in service_types:
            print(f"  - {service_type.name} (active={service_type.active})")

        today = date.today()
        availability = client.get_availability(from_=today, to=today + timedelta(days=14))
        print(f"Availability ({availability.timezone}): {len(availability.slots)} open slots in the next 14 days")

        if not availability.slots:
            print("No open slots in the next 14 days, cannot verify booking creation. Seed more availability and re-run.")
            return 0

        slot = availability.slots[0]
        print(f"Booking the first open slot: {slot.start_at.isoformat()}")
        try:
            booking = client.create_booking(
                start_at=slot.start_at,
                customer_name="Creno SDK Verification",
                customer_email=f"sdk-verify-{uuid.uuid4().hex[:8]}@example.com",
                notes="Created by scripts/verify_live.py, safe to delete.",
            )
        except CrenoError as exc:
            print(f"Booking failed: {exc.message} (status {exc.status_code})")
            return 1

        print(f"Booking created: id={booking.id} status={booking.status}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
