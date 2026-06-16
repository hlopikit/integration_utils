import functools
import time

from integration_utils.vendors.telegram.error import RetryAfter, TimedOut


def telegram_retry_decorator(attempts=3, timeout_delay=1):
    """
    Декоратор для повторных попыток Telegram-методов с общим лимитом попыток.

    Поведение:
    - при `RetryAfter` ждём `exc.retry_after`;
    - при `TimedOut` ждём `timeout_delay`;
    - все повторные вызовы считаются в общий `attempts`.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except (RetryAfter, TimedOut) as exc:
                    is_last_attempt = attempt == attempts
                    if is_last_attempt:
                        raise
                    delay = exc.retry_after if isinstance(exc, RetryAfter) else timeout_delay
                    if delay > 0:
                        time.sleep(delay)

        return wrapper

    return decorator
