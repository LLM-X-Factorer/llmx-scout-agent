"""Tiny retry helper with exponential backoff."""

import time
from collections.abc import Callable


def retry[T](
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
) -> T:
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if i == attempts - 1:
                break
            delay = min(max_delay, base_delay * (2**i))
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc
