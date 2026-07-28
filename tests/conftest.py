import httpx
import pytest

from creno import CrenoClient


@pytest.fixture
def client_with():
    """Builds a CrenoClient whose transport is a caller-supplied handler function.

    Usage: client_with(lambda request: httpx.Response(200, json=[]))
    """

    def make(handler) -> CrenoClient:
        return CrenoClient(api_key="pk_test_123", transport=httpx.MockTransport(handler))

    return make
