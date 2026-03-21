"""
Exponential backoff retry utility for platform API calls.
Retries on transient errors (429 rate limit, 5xx server errors).
"""
import asyncio
import random
import logging
from typing import Callable, Any

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


async def with_retry(
    fn: Callable,
    max_attempts: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    **kwargs,
) -> Any:
    """
    Call `fn(**kwargs)` up to `max_attempts` times with exponential backoff + jitter.
    Raises the last exception if all attempts fail.
    """
    last_exc: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return await fn(**kwargs)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code

            # Check for Retry-After header (rate limit)
            retry_after = exc.response.headers.get("Retry-After")

            if status in RETRYABLE_STATUS and attempt < max_attempts - 1:
                if retry_after:
                    delay = float(retry_after)
                else:
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)

                logger.warning(
                    "Attempt %d/%d failed with HTTP %d — retrying in %.1fs",
                    attempt + 1, max_attempts, status, delay,
                )
                await asyncio.sleep(delay)
                last_exc = exc
            else:
                raise  # permanent error or last attempt

        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            if attempt < max_attempts - 1:
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                logger.warning(
                    "Attempt %d/%d network error — retrying in %.1fs: %s",
                    attempt + 1, max_attempts, delay, exc,
                )
                await asyncio.sleep(delay)
                last_exc = exc
            else:
                raise

    raise last_exc  # type: ignore
