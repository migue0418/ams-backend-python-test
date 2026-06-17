import asyncio

import httpx
import pytest
import respx
from domain.models import NotificationRequestIn, NotificationType, RequestStatus
from domain.repository import InMemoryNotificationRepository
from services import pipeline, provider_client

NOTIFY_URL = "http://localhost:3001/v1/notify"


async def _wait_until_terminal(repo, request_id, timeout=5.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        record = repo.get(request_id)
        if record.status in (RequestStatus.sent, RequestStatus.failed):
            return record
        await asyncio.sleep(0.05)
    raise TimeoutError(f"{request_id} never reached a terminal state")


@pytest.fixture
async def repo():
    repository = InMemoryNotificationRepository()
    await provider_client.start()
    await pipeline.start(repository)
    yield repository
    await pipeline.stop()
    await provider_client.stop()


@respx.mock
async def test_enqueued_request_ends_up_sent(repo):
    respx.post(NOTIFY_URL).mock(
        return_value=httpx.Response(
            200,
            json={"status": "delivered", "provider_id": "p-1"},
        ),
    )
    record = repo.create(
        NotificationRequestIn(
            to="user@example.com",
            message="hi",
            type=NotificationType.email,
        ),
    )
    repo.start_processing(record.id)
    pipeline.enqueue(record.id)

    final = await _wait_until_terminal(repo, record.id)
    assert final.status == RequestStatus.sent


@respx.mock
async def test_enqueued_request_ends_up_failed_after_exhausting_retries(repo):
    respx.post(NOTIFY_URL).mock(return_value=httpx.Response(429))
    record = repo.create(
        NotificationRequestIn(
            to="user@example.com",
            message="hi",
            type=NotificationType.sms,
        ),
    )
    repo.start_processing(record.id)
    pipeline.enqueue(record.id)

    final = await _wait_until_terminal(repo, record.id, timeout=15.0)
    assert final.status == RequestStatus.failed
