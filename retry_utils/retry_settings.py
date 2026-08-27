import time
from typing import Any, Callable, Optional, Type, TypeVar, Tuple, Union


_CallableT = TypeVar("_CallableT", bound=Callable)


class RetrySettings:
    def __init__(
            self,
            attempts: int = 1,
            delay: float = 0,
            exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = (Exception,),
            should_retry: Optional[Callable[[Exception], bool]] = None,
    ):
        if attempts < 1:
            raise ValueError("attempts must be greater than 0")

        if delay < 0:
            raise ValueError("delay must be greater than or equal to 0")

        self.attempts = attempts
        self.delay = delay
        self.exceptions = exceptions if isinstance(exceptions, tuple) else (exceptions,)
        self.should_retry = should_retry

    def __call__(self, func: _CallableT) -> _CallableT:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for _ in range(self.attempts - 1):
                try:
                    return func(*args, **kwargs)
                except self.exceptions as exc:
                    if self.should_retry and not self.should_retry(exc):
                        raise

                    if self.delay:
                        time.sleep(self.delay)

            return func(*args, **kwargs)

        return wrapper
