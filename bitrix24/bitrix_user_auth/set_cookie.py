from typing import Optional, TypeVar

from django.conf import settings
from django.http.response import HttpResponseBase

from six.moves.http_cookies import CookieError


_Response = TypeVar('_Response', bound=HttpResponseBase)


def set_auth_cookie(response: _Response, user_token_sig: Optional[str] = None, max_age: Optional[int] = None) -> _Response:
    """Устанавливает cookie авторизации приложения Битрикс24 в HTTP-ответе.

    Имя cookie формируется на основе имени приложения, а её значением
    служит переданный подписанный идентификатор записи BitrixUserToken.
    Для работы внутри iframe устанавливаются атрибуты Secure и SameSite=None.

    :param response: HTTP-ответ, в который необходимо добавить cookie.
    :param user_token_sig: Подписанный идентификатор токена пользователя.
        Подпись должна быть сформирована вызывающим кодом.
    :param max_age: Срок действия cookie в секундах. Если не передан,
        используется settings.AUTH_COOKIE_MAX_AGE или 1800 секунд по умолчанию.
        При повторном использовании подписи можно передать оставшийся срок
        её действия, чтобы не продлевать исходную сессию.
    :return: Исходный HTTP-ответ с установленной cookie авторизации.
    """

    if max_age is None:
        max_age = getattr(settings, 'AUTH_COOKIE_MAX_AGE', 30 * 60)

    app_name = settings.APP_SETTINGS.app_name
    cookie_template = 'b24app_auth_{}'

    # Отдельное имя cookie для каждого приложения на одном домене.
    cookie_key = cookie_template.format(app_name)

    # Secure разрешает передачу cookie только по HTTPS и необходим
    # для использования SameSite=None в современных браузерах.
    response.set_cookie(
        cookie_key,
        user_token_sig,
        max_age=max_age,
        secure=True,  # required for chrome
    )

    # Приложение открывается внутри iframe на другом сайте (Битрикс24).
    # SameSite=None разрешает межсайтовую передачу cookie, если это
    # допускается политикой браузера. Сам по себе атрибут не защищает от CSRF.
    try:
        response.cookies[cookie_key]['samesite'] = 'None'
    except CookieError:
        # Совместимость со старыми реализациями http.cookies, в которых
        # SameSite отсутствует в списке допустимых атрибутов Morsel.
        # https://stackoverflow.com/a/50813092/2468136
        response.cookies[cookie_key]._reserved['samesite'] = 'None'

    return response
