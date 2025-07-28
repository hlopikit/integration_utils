import functools
import time

from integration_utils.vendors.telegram.error import RetryAfter


def telegram_retry_after(max_retries=1):
    """
    Для повторных попыток вызова функции при ошибке RetryAfter от Telegram.
    В случае ошибки делается пауза (длительность указана в ошибке).

    >>> # Пример использования
        @telegram_retry_after(max_retries=2)
        def test():
            print('Test')
            from integration_utils.vendors.telegram.error import RetryAfter
            raise RetryAfter(retry_after=3)

    :param max_retries: Максимальное количество повторных попыток.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for retry in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RetryAfter as e:
                    if retry >= max_retries:
                        raise e
                    time.sleep(e.retry_after)
        return wrapper
    return decorator
