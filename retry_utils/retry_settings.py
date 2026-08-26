import time
import typing


ExceptionClasses = typing.Union[typing.Type[BaseException], typing.Tuple[typing.Type[BaseException], ...]]
RetryPredicate = typing.Callable[[BaseException], bool]
CallableType = typing.TypeVar("CallableType", bound=typing.Callable)


class RetrySettings:
    def __init__(
            self,
            attempts: int = 1,
            delay: float = 0,
            exceptions: ExceptionClasses = (Exception,),
            should_retry: typing.Optional[RetryPredicate] = None,
    ):
        if attempts < 1:
            raise ValueError("attempts must be greater than 0")

        if delay < 0:
            raise ValueError("delay must be greater than or equal to 0")

        self.attempts = attempts
        self.delay = delay
        self.exceptions = exceptions if isinstance(exceptions, tuple) else (exceptions,)
        self.should_retry = should_retry

    def __call__(self, func: CallableType) -> CallableType:
        def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            for attempt in range(1, self.attempts + 1):
                try:
                    return func(*args, **kwargs)
                except self.exceptions as exc:
                    if self.should_retry and not self.should_retry(exc):
                        raise

                    if attempt >= self.attempts:
                        raise

                    if self.delay:
                        time.sleep(self.delay)

        return typing.cast(CallableType, wrapper)
