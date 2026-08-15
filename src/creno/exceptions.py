from __future__ import annotations

from typing import Any, Optional


class CrenoError(Exception):
    """Base class for every error this client raises.

    `status_code` is None for errors that never got an HTTP response at all
    (a network failure) rather than a non-2xx one.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        response_body: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body


class CrenoAuthenticationError(CrenoError):
    """401 - the X-API-Key header was missing or didn't match a real key."""


class CrenoForbiddenError(CrenoError):
    """403 - the request's Origin header isn't on the tenant's allowlist.

    This client never sends an Origin header, so this shouldn't occur during
    normal server-to-server use of this SDK.

    A suspended tenant also answers 403, as the subclass below. Catching this
    one still catches both.
    """


class CrenoTenantSuspendedError(CrenoForbiddenError):
    """403 with ``code: "tenant_suspended"`` - the business is suspended.

    Unlike the origin case above, this one *is* reachable from normal
    server-to-server use, and retrying will not help: the suspension is
    deliberate and only Creno can lift it.

    A subclass, so existing ``except CrenoForbiddenError`` code is unaffected.
    """


class CrenoNotFoundError(CrenoError):
    """404 - no matching resource, or no scheduling resource configured for this tenant."""


class CrenoValidationError(CrenoError):
    """400 - the request body failed validation (for example, a Turnstile challenge)."""


class CrenoConflictError(CrenoError):
    """409 - the requested time slot is no longer available."""


class CrenoPlanLimitError(CrenoError):
    """402 - the tenant's plan limit has been reached."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response_body: Any,
        limit_type: Optional[str],
        plan: Optional[str],
    ) -> None:
        super().__init__(message, status_code=status_code, response_body=response_body)
        self.limit_type = limit_type
        self.plan = plan


class CrenoRateLimitError(CrenoError):
    """429 - too many requests. Rate limits are keyed per API key, not per IP."""


class CrenoAPIError(CrenoError):
    """Fallback for network errors, 5xx responses, or any other unexpected response."""
