from functools import wraps

from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt

from integration_utils.bitrix24.bitrix_user_auth.authenticate_on_start_application import authenticate_on_start_application
from integration_utils.bitrix24.bitrix_user_auth.get_bitrix_user_token_from_cookie import get_bitrix_user_token_from_cookie, EmptyCookie
from integration_utils.bitrix24.bitrix_user_auth.get_bitrix_user_token_from_header import get_bitrix_user_token_from_header
from integration_utils.bitrix24.bitrix_user_auth.set_cookie import set_auth_cookie


def main_auth(on_start=False, on_cookies=False, on_header=False, set_cookie=False):
    # Для аутентификации пользователя портала
    # on_start - авторизация по первому входу из Битрикс24
    # on_cookies - авторизация по кукам = для гет запросов ОК
    # on_token - авторизация по токену, для POST-запросов и других влияющих на данные

    def inner_main_auth(func):
        @csrf_exempt
        @xframe_options_exempt
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Основная процедура авторизации
            if on_start:
                authenticate_on_start_application(request=request)
            if on_cookies:
                try:
                    get_bitrix_user_token_from_cookie(request)
                except EmptyCookie:
                    return render(request, 'empty_cookie_error.html', status=401)
            if on_header:
                get_bitrix_user_token_from_header(request=request)

            response = func(request, *args, **kwargs)
            if set_cookie:
                response = set_auth_cookie(response, request.bitrix_user_token.signed_pk())
            return response
        return wrapper
    return inner_main_auth
