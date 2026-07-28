# creno

Official Python client for [Creno](https://crenoapp.com)'s scheduling and booking API.

```python
from creno import CrenoClient

with CrenoClient(api_key="pk_live_...") as client:
    service_types = client.list_service_types()
    availability = client.get_availability(from_="2026-08-01", to="2026-08-07")
    booking = client.create_booking(
        start_at=availability.slots[0].start_at,
        customer_name="Jane Doe",
        customer_email="jane@example.com",
    )
```

## Install

```
pip install creno
```

Requires Python 3.9+. The only runtime dependency is [httpx](https://www.python-httpx.org/).

## Security model

The API key you pass to `CrenoClient` is the same "publishable" key used by Creno's browser widgets (`@creno/react`, `<creno-widget>`). In the browser, safety comes from Creno's per-tenant origin allowlist, not from keeping the key secret. This client makes server-to-server calls with no `Origin` header, so that allowlist check never applies here. Treat the key as sensitive in your own backend even though it's called "publishable" elsewhere.

## Errors

Every non-2xx response raises a subclass of `CrenoError` (`.message`, `.status_code`, `.response_body`):

| Exception | Status | Meaning |
|---|---|---|
| `CrenoAuthenticationError` | 401 | Missing or invalid API key |
| `CrenoForbiddenError` | 403 | Origin not on the tenant's allowlist (shouldn't occur for server-to-server calls) |
| `CrenoNotFoundError` | 404 | No matching resource, or no scheduling resource configured for this tenant |
| `CrenoValidationError` | 400 | Request failed validation (for example, a Turnstile challenge) |
| `CrenoConflictError` | 409 | The requested time slot is no longer available |
| `CrenoPlanLimitError` | 402 | The tenant's plan limit was reached, carries `.limit_type` and `.plan` |
| `CrenoRateLimitError` | 429 | Too many requests, rate-limited per API key rather than per IP |
| `CrenoAPIError` | any | Fallback for network errors or unexpected responses |

`list_service_types` and `get_availability` retry automatically (up to 3 attempts with backoff) on network errors or 5xx responses, since they're read-only. `create_booking` never retries automatically: a lost response after a booking was actually created server-side, followed by a client-side retry, could still submit a second real booking attempt for a real customer, even though Creno's own database can never double-book the same slot. If `create_booking` raises `CrenoAPIError` with an unclear outcome, check the tenant's Creno dashboard before retrying by hand.

## Dates and times

`Slot` and `Booking` fields are real timezone-aware `datetime.datetime` objects, already parsed from the API's ISO-8601 strings. `create_booking`'s `start_at` accepts either a timezone-aware `datetime` or an ISO-8601 string; a naive `datetime` (no `tzinfo`) raises `ValueError` rather than silently guessing a timezone. `get_availability`'s `from_`/`to` accept either a `datetime.date` or a `"YYYY-MM-DD"` string.

Optional fields you don't have, for example `resource_id` or `service_type_id`, should simply be omitted (their default is `None`). This client drops `None` values from the request body before sending, since Creno's API treats a field as "not provided" only when it's absent from the JSON body entirely, not when it's sent as `null`.

## License

[MIT](./LICENSE). See [CHANGELOG.md](./CHANGELOG.md) for release history and the repo root's [SECURITY.md](../../SECURITY.md) to report a vulnerability.

---

Made by [Solution Lancée](https://solutionlancee.com).
