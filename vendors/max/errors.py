from typing import Tuple


def _lstrip_str(value: str, prefix: str) -> str:
    if value.startswith(prefix):
        return value[len(prefix):]
    return value


class MaxError(Exception):
    """Базовый класс ошибок MAX API."""

    __slots__ = ("message", "status_code", "error_code", "response_data")

    def __init__(self, message: str, status_code=None, error_code=None, response_data=None):
        super().__init__()
        self.message = _lstrip_str(_lstrip_str(message, "Error: "), "[Error]: ")
        self.status_code = status_code
        self.error_code = error_code
        self.response_data = response_data

    def __str__(self) -> str:
        return self.message

    def __reduce__(self) -> Tuple[type, Tuple[str, int | None, str | None, dict | None]]:
        return self.__class__, (self.message, self.status_code, self.error_code, self.response_data)


class MaxUnauthorized(MaxError):
    """Недостаточно прав для выполнения действия."""

    __slots__ = ()


class MaxNetworkError(MaxError):
    """Сетевая ошибка при запросе к MAX API."""

    __slots__ = ()
