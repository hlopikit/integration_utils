"""Декоратор авторизации пользователей приложений Битрикс24."""

import time
from typing import Any, Callable, Optional, Set, TYPE_CHECKING

from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.signing import BadSignature, b62_decode
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.http.response import HttpResponseBase
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt

from integration_utils.bitrix24.bitrix_user_auth.authenticate_on_start_application import authenticate_on_start_application
from integration_utils.bitrix24.bitrix_user_auth.get_bitrix_user_token_from_cookie import get_bitrix_user_token_from_cookie, EmptyCookie
from integration_utils.bitrix24.bitrix_user_auth.get_bitrix_user_token_from_header import get_bitrix_user_token_from_header, InvalidHeader
from integration_utils.bitrix24.bitrix_user_auth.set_cookie import set_auth_cookie
from integration_utils.bitrix24.exceptions import BitrixApiError, BitrixApiException
from integration_utils.bitrix24.types import AuthRequest

from settings import ilogger

if TYPE_CHECKING:
    from integration_utils.bitrix24.models import BitrixUserToken


_SAFE_REDIRECT_METHODS: Set[str] = {'GET', 'HEAD'}
_View = Callable[..., HttpResponseBase]


def _marketplace_auth_redirect(request: HttpRequest) -> Optional[HttpResponseRedirect]:
    """Формирует перенаправление в приложение Marketplace для получения cookie.

    ID приложения берётся из настройки BITRIX_MARKETPLACE_AUTH_APP_ID.
    В return_to передаётся относительный URL исходного запроса вместе с query-параметрами,
    чтобы после авторизации start-view мог вернуть пользователя на нужную страницу.
    Вызывается только для безопасных методов, чтобы не потерять тело запроса.

    :param request: Исходный HTTP-запрос пользователя.
    :return: Ответ с перенаправлением или None, если ID приложения не задан или некорректен.
    """

    marketplace_auth_app_id = str(getattr(settings, 'BITRIX_MARKETPLACE_AUTH_APP_ID', ''))

    if not marketplace_auth_app_id.isdecimal():
        return None

    marketplace_url = f'https://{settings.APP_SETTINGS.portal_domain}/marketplace/app/{marketplace_auth_app_id}/'
    return HttpResponseRedirect(f'{marketplace_url}?{urlencode({"return_to": request.get_full_path()})}')


def _try_recent_signature(
        request: AuthRequest,
        signature: Optional[str],
        load_token: Callable[..., "BitrixUserToken"],
        max_age: int,
) -> bool:
    """Пытается восстановить авторизацию по ранее выданной подписи без REST-запросов.

    Проверку подписи, её возраста и поиск токена в БД выполняет load_token.
    При успехе функция загрузки также заполняет данные авторизации в request.
    Ожидаемые ошибки авторизации позволяют перейти к входу по данным запуска;
    остальные исключения передаются вызывающему коду.

    :param request: HTTP-запрос, в который записываются данные авторизации.
    :param signature: Подписанный идентификатор токена из cookie или заголовка.
    :param load_token: Функция восстановления авторизации из выбранного источника.
    :param max_age: Максимально допустимый возраст подписи в секундах.
    :return: True при успешной авторизации, иначе False.
    """

    if not signature:
        return False

    try:
        load_token(request, max_age=max_age)
    except (InvalidHeader, EmptyCookie, BadSignature, ObjectDoesNotExist, ValueError):
        return False
    else:
        return True


def _cookie_auth_error_response(request: HttpRequest) -> HttpResponse:
    """Формирует ответ при отсутствующей, просроченной или некорректной cookie.

    Для GET и HEAD по возможности перенаправляет пользователя в Marketplace.
    Для остальных методов и при отсутствии настроенного приложения возвращает 401.
    Это исключает потерю тела запроса при перенаправлении изменяющих операций.

    :param request: Исходный HTTP-запрос пользователя.
    :return: Ответ с перенаправлением или HTML-страница ошибки авторизации.
    """

    if request.method in _SAFE_REDIRECT_METHODS:
        redirect_response = _marketplace_auth_redirect(request)

        if redirect_response:
            return redirect_response

    return render(request, 'empty_cookie_error.html', status=401)


def main_auth(
        on_start: bool = False,
        on_cookies: bool = False,
        on_header: bool = False,
        set_cookie: bool = False,
        cookie_max_age: Optional[int] = None,
) -> Callable[[_View], _View]:
    """Создаёт декоратор авторизации пользователя портала Битрикс24.

    Режимы авторизации:
    - Только on_start: обязательная OAuth-авторизация по данным запуска приложения.
    - Только on_cookies: авторизация по подписанному идентификатору токена из cookie.
    - Только on_header: авторизация по заголовку X-Bitrix-Signed-Token без ограничения
      возраста подписи (для сохранения существующего поведения).
    - on_start + on_cookies: сначала проверка cookie, при неудаче — OAuth-авторизация.
    - on_start + on_header: сначала проверка заголовка, при неудаче — OAuth-авторизация.

    В комбинированных режимах действительная подпись позволяет пропустить REST-запросы
    к Битрикс24 даже при наличии нового AUTH_ID. До истечения подписи может использоваться
    ранее авторизованный пользователь, в том числе после смены пользователя на портале.
    on_cookies и on_header взаимоисключающие. Если все три флага выключены,
    проверка авторизации не выполняется.

    Декоратор отключает CSRF-проверку и разрешает отображение страницы в iframe.
    Для обработчиков, изменяющих данные, следует использовать авторизацию по заголовку
    либо обеспечить отдельную CSRF-защиту при использовании cookie. Сам декоратор
    не ограничивает авторизацию по cookie HTTP-методами.

    :param on_start: Разрешить OAuth-авторизацию по данным запуска приложения.
    :param on_cookies: Использовать подписанный идентификатор токена из cookie.
    :param on_header: Использовать подписанный идентификатор токена из HTTP-заголовка.
    :param set_cookie: Установить cookie после успешного выполнения представления.
        В комбинированном режиме при повторном использовании подписи сохраняется
        её исходный срок действия; в остальных случаях создаётся новая подпись.
    :param cookie_max_age: Срок действия cookie и максимальный возраст подписи
        при авторизации по cookie или в комбинированном режиме, в секундах.
        По умолчанию используется settings.AUTH_COOKIE_MAX_AGE или 1800 секунд.
    :return: Декоратор Django-представления.
    :raises ValueError: Если одновременно включены on_cookies и on_header.
    """

    if on_cookies and on_header:
        raise ValueError("main_auth: on_cookies и on_header нельзя включать одновременно")

    # Явно переданный срок имеет приоритет над настройкой проекта и значением по умолчанию.
    if cookie_max_age is None:
        cookie_max_age = getattr(settings, 'AUTH_COOKIE_MAX_AGE', 30 * 60)

    def error_response(
            request: HttpRequest,
            message: str,
            status: int,
            code: str,
            template: str = 'bitrix_auth_error.html',
    ) -> HttpResponse:
        """Формирует JSON-ошибку для режима on_header или HTML-страницу для остальных.

        :param request: Исходный HTTP-запрос пользователя.
        :param message: Описание ошибки для пользователя.
        :param status: HTTP-статус ответа.
        :param code: Машиночитаемый код ошибки для JSON-ответа.
        :param template: Имя шаблона HTML-страницы ошибки.
        :return: HTTP-ответ с описанием ошибки авторизации.
        """

        if on_header:
            return JsonResponse(
                data={
                    'error': code,
                    'error_description': message,
                },
                status=status,
            )

        return render(
            request=request,
            template_name=template,
            context={
                'error_message': message,
            },
            status=status,
        )

    def inner_main_auth(func: _View) -> _View:
        """Оборачивает представление проверкой авторизации с заданными параметрами.

        :param func: Исходное Django-представление.
        :return: Представление с проверкой авторизации и установкой cookie при необходимости.
        """

        # Приложение открывается внутри iframe Битрикс24, в том числе через внешний POST.
        @csrf_exempt
        @xframe_options_exempt
        @wraps(func)
        def wrapper(request: AuthRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
            """Авторизует пользователя, вызывает представление и при необходимости устанавливает cookie.

            :param request: HTTP-запрос, дополняемый данными авторизации.
            :param args: Позиционные аргументы представления.
            :param kwargs: Именованные аргументы представления.
            :return: Ответ представления либо ответ с ошибкой авторизации.
            """

            # Сохраняем исходную подпись только при успешной локальной авторизации
            # в комбинированном режиме, чтобы впоследствии не продлить её срок жизни.
            saved_signature: Optional[str] = None

            try:
                # Комбинированный режим: сначала используем выбранный локальный источник
                # авторизации. Новый AUTH_ID не требует REST-проверки, пока подпись действительна.
                if on_start and (on_cookies or on_header):
                    if on_header:
                        signature = request.headers.get('X-Bitrix-Signed-Token')
                        load_token = get_bitrix_user_token_from_header
                    else:
                        cookie_name = f'b24app_auth_{settings.APP_SETTINGS.app_name}'
                        signature = request.COOKIES.get(cookie_name)
                        load_token = get_bitrix_user_token_from_cookie

                    if _try_recent_signature(request, signature, load_token, cookie_max_age):
                        saved_signature = signature
                    else:
                        # Нет действительной подписи — выполняем полноценную OAuth-авторизацию
                        # по данным запуска. Если их тоже нет, функция авторизации вернёт ошибку.
                        authenticate_on_start_application(request=request)
                else:
                    # Одиночные режимы не предусматривают переход на другой способ авторизации.
                    if on_start:
                        authenticate_on_start_application(request=request)

                    if on_cookies:
                        try:
                            get_bitrix_user_token_from_cookie(request, max_age=cookie_max_age)
                        except (BadSignature, EmptyCookie, ObjectDoesNotExist, ValueError):
                            return _cookie_auth_error_response(request)

                # В режиме только on_header сохраняется проверка подписи без max_age.
                # В комбинированном режиме заголовок уже проверен выше либо выполнен OAuth-вход.
                if on_header and not on_start:
                    try:
                        get_bitrix_user_token_from_header(request=request)
                    except (InvalidHeader, BadSignature, ObjectDoesNotExist, ValueError):
                        return error_response(request, 'Токен в заголовке отсутствует или недействителен.', 401, 'invalid_token')

            # Ошибки авторизации преобразуются в HTTP-ответы до вызова представления.
            except PermissionDenied:
                return error_response(request, 'Откройте приложение через портал Битрикс24.', 403, 'permission_denied')

            except BitrixApiError as exc:
                if exc.is_invalid_token:
                    return error_response(request, exc.friendly_error, 401, 'invalid_token', 'invalid_token_error.html')
                return error_response(request, exc.friendly_error, 502, 'bitrix_api_error')

            except BitrixApiException as exc:
                return error_response(request, exc.friendly_error, 502, 'bitrix_api_error')

            except Exception as exc:
                ilogger.error('bitrix_main_auth_error', str(exc))
                return error_response(request, 'Внутренняя ошибка авторизации приложения.', 500, 'internal_auth_error')

            # Представление выполняется вне блока обработки ошибок авторизации:
            # его собственные исключения не должны маскироваться как ошибки входа.
            response = func(request, *args, **kwargs)

            if set_cookie:
                if saved_signature:
                    # TimestampSigner хранит время создания подписи в формате base62:
                    # значение:время:подпись. Восстанавливаем исходное время и вычисляем
                    # остаток срока действия, а не выдаём новую подпись на полный период.
                    # Минимум в одну секунду учитывает округление и время работы представления;
                    # серверная проверка возраста исходной подписи при этом не изменяется.
                    signed_at = b62_decode(saved_signature.rsplit(':', 2)[1])
                    seconds_left = max(1, int(cookie_max_age - (time.time() - signed_at)))
                    response = set_auth_cookie(response, saved_signature, max_age=seconds_left)
                else:
                    # После OAuth-входа или в одиночном режиме выдаём новую подпись
                    # с полным сроком действия cookie.
                    response = set_auth_cookie(response, request.bitrix_user_token.signed_pk(), max_age=cookie_max_age)

            return response

        return wrapper

    return inner_main_auth
