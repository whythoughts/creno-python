# Changelog

All notable changes to the `creno` Python package are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [SemVer](https://semver.org/).

## [0.1.0] - 2026-07-28

### Added
- `CrenoClient`: typed, synchronous client (`httpx`-based) covering
  `fetch_service_types`, `fetch_availability`, and `create_booking`.
- A typed exception per API error code, `CrenoConflictError` (409),
  `CrenoPlanLimitError` (402), `CrenoRateLimitError` (429),
  `CrenoValidationError`, `CrenoNotFoundError`, `CrenoForbiddenError`,
  `CrenoAuthenticationError`, and a `CrenoAPIError` base for anything else, so callers can catch the specific failure they care about instead of
  parsing status codes by hand.
- Full type hints (`py.typed`), Python 3.9-3.13.
- Every request identifies itself via `X-Client-Library: python` and a
  `creno-python/{version}` User-Agent.

### Changed
- Relicensed to **MIT** (was file-based custom license metadata).
