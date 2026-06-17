import httpx
import pytest
import respx
from domain.models import NotificationRecord, NotificationType
from services import provider_client
from services.provider_client import ProviderError, RetryableProviderError

NOTIFY_URL = "http://localhost:3001/v1/notify"


def _record() -> NotificationRecord:
    return NotificationRecord(
        id="abc123",
        to="user@example.com",
        message="hi",
        type=NotificationType.email,
    )


@pytest.fixture(autouse=True)
async def _provider_client_lifecycle():
    await provider_client.start()
    yield
    await provider_client.stop()


@respx.mock
async def test_send_notification_succeeds_on_first_try():
    route = respx.post(NOTIFY_URL).mock(
        return_value=httpx.Response(
            200,
            json={"status": "delivered", "provider_id": "p-1"},
        ),
    )
    await provider_client.send_notification(_record())
    assert route.call_count == 1


@respx.mock
async def test_retries_transient_failures_then_succeeds():
    route = respx.post(NOTIFY_URL).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(429),
            httpx.Response(200, json={"status": "delivered", "provider_id": "p-1"}),
        ],
    )
    await provider_client.send_notification(_record())
    assert route.call_count == 3


@respx.mock
async def test_exhausts_retries_and_raises_retryable_error():
    respx.post(NOTIFY_URL).mock(return_value=httpx.Response(429))
    with pytest.raises(RetryableProviderError):
        await provider_client.send_notification(_record())


@respx.mock
async def test_non_retryable_response_fails_without_retrying():
    route = respx.post(NOTIFY_URL).mock(return_value=httpx.Response(401))
    with pytest.raises(ProviderError):
        await provider_client.send_notification(_record())
    assert route.call_count == 1
