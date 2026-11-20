import functools
import time

from integration_utils.vendors.telegram.error import RetryAfter, TelegramError


def telegram_retry_decorator(attempts: int = 3, timeout_delay: float = 1):
    """
    Декоратор повторных попыток Telegram-методов.

    - RetryAfter: задержка из retry_after.
    - NetworkError: задержка timeout_delay.
    - Логические ошибки не повторяются.
    - Все вызовы учитываются в общем лимите attempts.
    """

    if attempts < 1:
        raise ValueError('telegram_retry_decorator attempts must be >= 1')

    if timeout_delay < 0:
        raise ValueError('telegram_retry_decorator timeout_delay must be >= 0')

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, attempts):
                try:
                    return func(*args, **kwargs)
                except TelegramError as exc:
                    if not exc.is_not_logic_error:
                        raise

                    delay = exc.retry_after if isinstance(exc, RetryAfter) else timeout_delay

                    if delay > 0:
                        time.sleep(delay)

            return func(*args, **kwargs)

        return wrapper

    return decorator
