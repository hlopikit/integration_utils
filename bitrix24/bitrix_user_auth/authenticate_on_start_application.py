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

    # Заполнение полей токена
    bitrix_user_token.user = user
    bitrix_user_token.auth_token = auth_token

    if refresh_token:
        bitrix_user_token.refresh_token = refresh_token

    bitrix_user_token.auth_token_date = timezone.now()
    bitrix_user_token.is_active = True
    bitrix_user_token.refresh_error = 0
    if app_sid is not None:
        bitrix_user_token.app_sid = app_sid
    bitrix_user_token.save()

    # Информацию о пользователе и портале записать в объект request
    # Она будет использована в функциях, у которых есть данный декоратор
    request.bitrix_user = user
    request.bitrix_user_is_new = user_created
    request.bitrix_user_token = bitrix_user_token
