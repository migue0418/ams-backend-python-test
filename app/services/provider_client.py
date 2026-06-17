import httpx
from core.config import settings
from domain.models import NotificationRecord
from services.rate_limiter import SlidingWindowRateLimiter
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

NOTIFY_PATH = "/v1/notify"

_client: httpx.AsyncClient | None = None
_rate_limiter = SlidingWindowRateLimiter(
    max_requests=settings.rate_limit_max_requests,
    window_seconds=settings.rate_limit_window_seconds,
)


# split so tenacity only retries the transient one, not e.g. a bad API key
class ProviderError(Exception):
    """Non-retryable provider failure (e.g. unexpected/auth response)."""


class RetryableProviderError(ProviderError):
    """Transient provider failure (429/500/timeout/connection), safe to retry."""


async def start() -> None:
    # reused across calls so connections get pooled instead of reconnecting every time
    global _client
    _client = httpx.AsyncClient(
        base_url=settings.provider_base_url,
        timeout=settings.provider_timeout_seconds,
    )


async def stop() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


# jitter matters here: without it, workers that fail together (e.g. a 429 trip) would all retry in lockstep
@retry(
    retry=retry_if_exception_type(RetryableProviderError),
    wait=wait_exponential_jitter(
        initial=settings.retry_wait_initial_seconds,
        max=settings.retry_wait_max_seconds,
    ),
    stop=stop_after_attempt(settings.retry_max_attempts),
    reraise=True,
)
async def send_notification(record: NotificationRecord) -> None:
    """Send to the provider; raises if it never succeeds after retries."""
    assert _client is not None, (
        "provider_client.start() must run before send_notification()"
    )

    await _rate_limiter.acquire()
    try:
        response = await _client.post(
            NOTIFY_PATH,
            json={
                "to": record.to,
                "message": record.message,
                "type": record.type.value,
            },
            params={
                "trace_id": record.id,
            },  # so provider logs line up with our request id
            headers={"X-API-Key": settings.provider_api_key},
        )
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise RetryableProviderError(str(exc)) from exc

    if response.status_code == 200:
        return
    if response.status_code in (429, 500):
        raise RetryableProviderError(f"provider returned {response.status_code}")
    raise ProviderError(
        f"unexpected provider response {response.status_code}: {response.text}",
    )
