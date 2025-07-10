import functools
import time

from integration_utils.vendors.telegram.error import RetryAfter


def telegram_retry_after(max_retries=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for retry in range(0, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RetryAfter as e:
                    if retry >= max_retries:
                        raise e
                    time.sleep(e.retry_after)
        return wrapper
    return decorator
