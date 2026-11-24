from typing import Optional

from integration_utils.bitrix24.models import BitrixUserToken
from integration_utils.bitrix24.types import AuthRequest


class InvalidHeader(Exception):
    """Заголовок авторизации отсутствует или пуст."""
    pass


def get_bitrix_user_token_from_header(request: AuthRequest, max_age: Optional[int] = None) -> BitrixUserToken:
    """Авторизует пользователя по подписанному идентификатору токена из заголовка.

    Проверяет подпись, получает токен из локальной БД и записывает данные
    авторизации в объект request. REST-запросы к Битрикс24 не выполняются.

    :param request: HTTP-запрос с заголовком X-Bitrix-Signed-Token.
    :param max_age: Максимальный возраст подписи в секундах. Если не задан,
        срок действия подписи не проверяется.
    :return: Найденный токен пользователя Битрикс24.
    :raises InvalidHeader: Если заголовок отсутствует или содержит пустое значение.
    :raises BadSignature: Если подпись недействительна или истёк заданный срок её действия.
    :raises BitrixUserToken.DoesNotExist: Если токен не найден в локальной БД.
    """

    bitrix_user_token_signed_pk = request.headers.get('X-Bitrix-Signed-Token')

    if bitrix_user_token_signed_pk:
        # Проверяем подписанный PK и загружаем существующий токен из БД.
        request.bitrix_user_token = BitrixUserToken.get_by_signed_pk(bitrix_user_token_signed_pk, max_age=max_age)
        # Заполняем контекст авторизации для представления без создания пользователя.
        request.bitrix_user = request.bitrix_user_token.user
        request.bitrix_user_is_new = False

        return request.bitrix_user_token
    else:
        raise InvalidHeader()
