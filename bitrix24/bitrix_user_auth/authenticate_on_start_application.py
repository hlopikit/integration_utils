from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.http import HttpResponse
from django.utils import timezone
from integration_utils.bitrix24.models import BitrixUserToken, BitrixUser


def authenticate_on_start_application(request):

    # на базе разнообразных параметров в iframe определяет пользователя и сохраняет в request
    #
    #request.bitrix_user
    #request.bitrix_user_is_new
    #request.bitrix_user_token

    # Это для входа через IFRAME
    auth_token = request.POST.get('AUTH_ID')
    refresh_token = request.POST.get('REFRESH_ID')
    app_sid = request.GET.get('APP_SID')
    https = request.GET.get('PROTOCOL', '1') == '1'

    if not auth_token and request.POST.get('auth[access_token]'):
        # Для авторизации ЧатБотов
        auth_token = request.POST.get('auth[access_token]')
        refresh_token = request.POST.get('auth[refresh_token]')

    if not auth_token:
        raise PermissionDenied(f"Не передан AUTH_ID. Ожидаем что этот урл будет открываться через фрейм в Битрикс24. ")

    request.bitrix_user_is_new = None
    request.bitrix_auth_key = None
    request.bitrix_user = None

    dynamic_token = BitrixUserToken(auth_token=auth_token)
    user_info = dynamic_token.call_api_method('user.current')['result']
    admin_info = dynamic_token.call_api_method('user.admin')['result']

    user, user_created = BitrixUser.objects.get_or_create(bitrix_id=int(user_info['ID']))

    # Обновить основную информацию о пользователе
    user.update_from_bitrix_response(user=user_info, save=False)

    # Обновление прочих полей пользователя
    user.is_admin = admin_info  # админ ли юзер?
    user.user_is_active = True  # если дошел до сюда - точно активный
    user.save()

    # Получение или инициализация токена из БД
    try:
        bitrix_user_token = BitrixUserToken.objects.get(user=user)
    except BitrixUserToken.DoesNotExist:
        bitrix_user_token = BitrixUserToken()

    def _fill_token(but: BitrixUserToken):
        # Заполнение полей токена
        but.user = user
        but.auth_token = auth_token

        if refresh_token:
            but.refresh_token = refresh_token

        but.auth_token_date = timezone.now()
        but.is_active = True
        but.refresh_error = 0
        if app_sid is not None:
            but.app_sid = app_sid

    _fill_token(bitrix_user_token)

    try:
        bitrix_user_token.save()
    except IntegrityError:
        # Случай, когда запросы накладываются друг на друга и получается два токена с одним юзером
        bitrix_user_token = BitrixUserToken.objects.get(user=user)
        _fill_token(bitrix_user_token)
        bitrix_user_token.save()

    # Информацию о пользователе и портале записать в объект request
    # Она будет использована в функциях, у которых есть данный декоратор
    request.bitrix_user = user
    request.bitrix_user_is_new = user_created
    request.bitrix_user_token = bitrix_user_token
