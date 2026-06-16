import functools
import time

from integration_utils.vendors.telegram.error import RetryAfter, TimedOut


def telegram_retry_decorator(attempts: int = 3, timeout_delay: int = 1):
    """
    Декоратор для повторных попыток Telegram-методов с общим лимитом попыток.

    Поведение:
    - при `RetryAfter` ждём `exc.retry_after`;
    - при `TimedOut` ждём `timeout_delay`;
    - все повторные вызовы считаются в общий `attempts`.
    """
    if attempts < 1:
        raise ValueError('telegram_retry_decorator attempts must be >= 1')

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
                    delay = getattr(exc, 'retry_after', timeout_delay)
                    if delay > 0:
                        time.sleep(delay)

        return wrapper

    return decorator
