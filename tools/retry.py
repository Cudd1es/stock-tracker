import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

def with_retry(func: Callable[[], T], attempts: int = 3, base_delay: float = 1.0,
               sleep: Callable[[float], None] = time.sleep) -> T:
    """
    call func, retrying on any exception with exponential backoff (1s, 2s, 4s...).
    re-raises the last exception once attempts are exhausted.
    """
    for n in range(1, attempts + 1):
        try:
            return func()
        except Exception as e:
            if n == attempts:
                raise
            delay = base_delay * 2 ** (n - 1)
            logger.warning("attempt %d/%d failed (%s), retrying in %.1fs", n, attempts, e, delay)
            sleep(delay)
    raise RuntimeError("unreachable")
