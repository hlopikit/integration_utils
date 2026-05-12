import typing

from django.http import HttpRequest

if typing.TYPE_CHECKING:
    from .models import (
        BitrixUser,
        BitrixUserToken,
    )

__all__ = [
    "ItsRequest",
    "AuthRequest",
]


class ItsRequest(HttpRequest):
    """Базовый request проекта."""

    its_error_response: bool
    """Флаг для ExcludeItsErrorResponseFilter."""


class AuthRequest(ItsRequest):
    """Request после main_auth или market_auth."""

    bitrix_user_token: typing.Optional["BitrixUserToken"]
    """Токен пользователя Bitrix."""

    bitrix_user: typing.Optional["BitrixUser"]
    """Пользователь Bitrix."""

    bitrix_user_is_new: typing.Optional[bool]
    """Новый ли пользователь."""
