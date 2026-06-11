import functools

from integration_utils.itsolution.decorators.telegram_retry_after import telegram_retry_after
from integration_utils.iu_retry_manager.retry_decorator import retry_decorator
from integration_utils.vendors.telegram.error import TimedOut


def telegram_retry_decorator(retry_after_retries=2, timeout_attempts=3, timeout_delay=0):
    """
    Единый декоратор для повторных попыток Telegram-методов.

    Логика разделена по типам временных ошибок:
    - для `RetryAfter` ждём столько, сколько вернул Telegram;
    - для `TimedOut` делаем обычные повторные попытки с фиксированной задержкой.

    Такой декоратор нужен для send/edit-методов, где хочется использовать одну точку
    подключения retry-логики, а не вешать два разных декоратора на каждый метод.
    """
    def decorator(func):
        decorated = telegram_retry_after(max_retries=retry_after_retries)(
            retry_decorator(
                attempts=timeout_attempts,
                exceptions=(TimedOut,),
                delay=timeout_delay,
            )(func)
        )
        return functools.wraps(func)(decorated)

    return decorator
