from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.signing import BadSignature
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt

from integration_utils.bitrix24.bitrix_user_auth.authenticate_on_start_application import authenticate_on_start_application
from integration_utils.bitrix24.bitrix_user_auth.get_bitrix_user_token_from_cookie import get_bitrix_user_token_from_cookie, EmptyCookie
from integration_utils.bitrix24.bitrix_user_auth.get_bitrix_user_token_from_header import get_bitrix_user_token_from_header
from integration_utils.bitrix24.bitrix_user_auth.set_cookie import set_auth_cookie
from integration_utils.bitrix24.exceptions import BitrixApiError


_SAFE_REDIRECT_METHODS = {'GET', 'HEAD'}


def _marketplace_auth_redirect(request):
    """Открывает приложение Marketplace, которое создаёт main_auth-cookie.

    ID приложения берётся из настройки проекта `BITRIX_MARKETPLACE_AUTH_APP_ID`.
    После iframe-запуска start-view вернёт браузер только на относительный путь
    текущего запроса. Переадресация допустима лишь для безопасных методов:
    POST/PUT нельзя превращать в GET, теряя тело операции.
    """
    marketplace_auth_app_id = str(getattr(settings, 'BITRIX_MARKETPLACE_AUTH_APP_ID', ''))
    if not marketplace_auth_app_id.isdecimal():
        return None
    marketplace_url = f'https://{settings.APP_SETTINGS.portal_domain}/marketplace/app/{marketplace_auth_app_id}/'
    return HttpResponseRedirect(f'{marketplace_url}?{urlencode({"return_to": request.get_full_path()})}')


def _cookie_auth_error_response(request):
    """Возвращает браузер на авторизацию либо прежний 401 для небезопасного запроса."""
    if request.method in _SAFE_REDIRECT_METHODS:
        redirect_response = _marketplace_auth_redirect(request)
        if redirect_response:
            return redirect_response
    return render(request, 'empty_cookie_error.html', status=401)


def main_auth(on_start=False, on_cookies=False, on_header=False, set_cookie=False):
    # Для аутентификации пользователя портала
    # on_start - авторизация по первому входу из Битрикс24
    # on_cookies - авторизация по кукам, для GET запросов
    # on_header - авторизация по токену, для POST запросов и других влияющих на данные
    # set_cookie - поставить куки в браузере для дальнейшей авторизации по on_cookies

    def inner_main_auth(func):
        @csrf_exempt
        @xframe_options_exempt
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Основная процедура авторизации
            if on_start:
                try:
                    authenticate_on_start_application(request=request)
                except BitrixApiError as exc:
                    if exc.is_invalid_token:
                        return render(request, 'invalid_token_error.html', status=401)
                    raise
            if on_cookies:
                try:
                    get_bitrix_user_token_from_cookie(request)
                except (BadSignature, EmptyCookie, ObjectDoesNotExist, ValueError):
                    return _cookie_auth_error_response(request)
            if on_header:
                get_bitrix_user_token_from_header(request=request)

            response = func(request, *args, **kwargs)
            if set_cookie:
                response = set_auth_cookie(response, request.bitrix_user_token.signed_pk())
            return response
        return wrapper
    return inner_main_auth
