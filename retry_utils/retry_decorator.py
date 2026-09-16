import functools
import time
from typing import Any, Callable, Iterable, Optional, Type, TypeVar, Union


_CallableT = TypeVar("_CallableT", bound=Callable)
_ExceptionType = Type[Exception]
_Exceptions = Union[_ExceptionType, Iterable[_ExceptionType]]


class RetryDecorator:
    def __init__(
            self,
            attempts: int = 1,
            delay: float = 0,
            exceptions: _Exceptions = (Exception,),
            exclude_exceptions: _Exceptions = (),
            should_retry: Optional[Callable[[Exception], bool]] = None,
            silent: bool = False,
    ):
        if attempts < 1:
            raise ValueError("attempts must be greater than 0")

        if delay < 0:
            raise ValueError("delay must be greater than or equal to 0")

        self.attempts = attempts
        self.delay = delay

        self.exceptions = (
            (exceptions,)
            if isinstance(exceptions, type)
            else tuple(exceptions)
        )
        self.exclude_exceptions = (
            (exclude_exceptions,)
            if isinstance(exclude_exceptions, type)
            else tuple(exclude_exceptions)
        )

        self.should_retry = should_retry
        self.silent = silent

    def __call__(self, func: _CallableT) -> _CallableT:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(1, self.attempts + 1):
                try:
                    return func(*args, **kwargs)
                except self.exceptions as exc:
                    if isinstance(exc, self.exclude_exceptions):
                        raise

                    if self.should_retry and not self.should_retry(exc):
                        raise

                    if attempt == self.attempts:
                        if self.silent:
                            return None
                        raise

                    if self.delay:
                        time.sleep(self.delay)

        return wrapper
