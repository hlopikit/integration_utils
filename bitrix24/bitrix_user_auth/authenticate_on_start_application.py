from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from integration_utils.bitrix24.exceptions import BatchApiCallError, BitrixApiException, get_bitrix_api_error
from integration_utils.bitrix24.models import BitrixUserToken, BitrixUser
from integration_utils.bitrix24.types import AuthRequest


def authenticate_on_start_application(request: AuthRequest):
    """Выполняет полноценную OAuth-авторизацию при запуске приложения из Битрикс24.

    Получает OAuth-данные из запроса iframe или чат-бота, определяет пользователя
    и его административные права через REST API Битрикс24, обновляет локальные
    данные пользователя и создаёт либо обновляет его токен авторизации.
    Записывает пользователя, признак его создания и токен в объект request
    для дальнейшего использования в представлении.

    Используется декоратором main_auth с параметром on_start=True,
    в том числе при невозможности авторизации по cookie или заголовку
    в комбинированных режимах.

    :param request: HTTP-запрос с OAuth-данными, переданными Битрикс24.
    :raises PermissionDenied: Если в запросе отсутствует токен доступа.
    :raises BitrixApiException: Если не удалось получить данные пользователя или его права.
    """

    # Стандартные параметры OAuth при запуске приложения в iframe.
    auth_token = request.POST.get('AUTH_ID')
    refresh_token = request.POST.get('REFRESH_ID')
    expires_in_seconds = request.POST.get('AUTH_EXPIRES')
    app_sid = request.GET.get('APP_SID')
    _https = request.GET.get('PROTOCOL', '1') == '1'

    if not auth_token and request.POST.get('auth[access_token]'):
        # Чат-боты передают OAuth-токены в другом формате. Используем его,
        # если стандартный AUTH_ID отсутствует.
        auth_token = request.POST.get('auth[access_token]')
        refresh_token = request.POST.get('auth[refresh_token]')

    if not auth_token:
        raise PermissionDenied(f"Не передан AUTH_ID. Ожидаем что этот урл будет открываться через фрейм в Битрикс24. ")

    # Сбрасываем данные предыдущей авторизации перед определением пользователя.
    request.bitrix_user_is_new = None
    request.bitrix_auth_key = None
    request.bitrix_user = None

    # Временный экземпляр токена позволяет обратиться к REST API до того,
    # как пользователь и его токен будут найдены или созданы в локальной БД.
    dynamic_token = BitrixUserToken(auth_token=auth_token)

    # Получаем профиль и административные права одним HTTP-запросом к batch.
    try:
        batch_result = dynamic_token.batch_api_call(
            methods=[
                ('user_info', 'user.current', None),
                ('admin_info', 'user.admin', None),
            ],
            halt=1,
        )
    except BatchApiCallError as exc:
        # Сохраняем обработку ошибок REST API в main_auth, включая invalid_token.
        raise exc.bitrix_api_error from exc

    # Ошибки отдельных команд batch возвращаются в результате, а не исключением.
    # HTTP-статус отдельной команды неизвестен, поэтому используем условный 400.
    for name, error in batch_result.iter_errors():
        raise get_bitrix_api_error(
            json_response=error,
            status_code=400,
            message=f'Ошибка команды batch: {name}',
        )

    user_info = batch_result['user_info']['result']
    admin_info = batch_result['admin_info']['result']

    # False — корректный результат user.admin для обычного пользователя.
    # Отсутствующий или некорректный результат не должен приводить к авторизации.
    if not isinstance(user_info, dict) or not user_info.get('ID') or not isinstance(admin_info, bool):
        raise BitrixApiException('Некорректный результат user.current или user.admin')

    # Сопоставляем пользователя Битрикс24 с локальной записью по его ID.
    user, is_user_created = BitrixUser.objects.get_or_create(bitrix_id=int(user_info['ID']))

    # Обновляем профиль без промежуточного сохранения в БД.
    user.update_from_bitrix_response(user=user_info, save=False)

    # Обновляем административные права и отмечаем пользователя активным
    # после успешных REST-запросов. Все изменения профиля сохраняем вместе.
    user.is_admin = admin_info
    user.user_is_active = True
    user.save()

    # Успешная авторизация обновляет токен доступа, сбрасывает счётчик
    # ошибок обновления токена и восстанавливает признак его активности.
    defaults = {
        'auth_token': auth_token,
        'auth_token_date': timezone.now(),
        'refresh_error': 0,
        'is_active': True,
    }

    # Не перезаписываем ранее сохранённые refresh_token и app_sid пустыми
    # значениями, если Битрикс24 не передал их при текущем запуске.
    if refresh_token:
        defaults['refresh_token'] = refresh_token

    if app_sid:
        defaults['app_sid'] = app_sid

    # AUTH_EXPIRES содержит срок жизни токена в секундах, а в БД хранится
    # абсолютное время его истечения. Если параметр отсутствует, сохраняем None.
    defaults['expires'] = timezone.now() + timedelta(seconds=int(expires_in_seconds)) if expires_in_seconds else None

    # Обновляем существующий токен пользователя или создаём новый.
    bitrix_user_token, _ = BitrixUserToken.objects.update_or_create(
        user=user,
        defaults=defaults,
    )

    # Передаём результат авторизации в представление через атрибуты request.
    # Декоратор main_auth также использует сохранённый токен для формирования cookie.
    request.bitrix_user = user
    request.bitrix_user_is_new = is_user_created
    request.bitrix_user_token = bitrix_user_token
