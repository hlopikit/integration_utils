from typing import Optional

from django.conf import settings

from integration_utils.bitrix24.models import BitrixUserToken
from integration_utils.bitrix24.types import AuthRequest


class EmptyCookie(Exception):
    """Cookie авторизации приложения отсутствует или пуста."""
    pass


def get_bitrix_user_token_from_cookie(request: AuthRequest, max_age: Optional[int] = None) -> BitrixUserToken:
    """Авторизует пользователя по подписанному идентификатору токена из cookie.

    Проверяет подпись и её срок действия, получает токен из локальной БД
    и записывает данные авторизации в объект request. REST-запросы
    к Битрикс24 не выполняются.

    :param request: HTTP-запрос с cookie авторизации приложения.
    :param max_age: Максимальный возраст подписи в секундах. Если не задан,
        используется settings.AUTH_COOKIE_MAX_AGE (по умолчанию 30 минут).
    :return: Найденный токен пользователя Битрикс24.
    :raises EmptyCookie: Если cookie отсутствует или содержит пустое значение.
    :raises BadSignature: Если подпись недействительна или срок её действия истёк.
    :raises BitrixUserToken.DoesNotExist: Если токен не найден в локальной БД.
    """

    if max_age is None:
        max_age = getattr(settings, 'AUTH_COOKIE_MAX_AGE', 30 * 60)

    # Имя cookie зависит от приложения, чтобы не смешивать их авторизацию.
    auth_cookie = f'b24app_auth_{settings.APP_SETTINGS.app_name}'
    bitrix_user_token_signed_pk = request.COOKIES.get(auth_cookie)

    if bitrix_user_token_signed_pk:
        # Проверяем подписанный PK и загружаем существующий токен из БД.
        request.bitrix_user_token = BitrixUserToken.get_by_signed_pk(bitrix_user_token_signed_pk, max_age=max_age)
        # Заполняем контекст авторизации для представления без создания пользователя.
        request.bitrix_user = request.bitrix_user_token.user
        request.bitrix_user_is_new = False

        return request.bitrix_user_token
    else:
        raise EmptyCookie()
