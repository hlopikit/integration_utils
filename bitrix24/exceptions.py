import six
from requests import Response
from django.http import JsonResponse

STRING_TYPES = six.string_types
INTEGER_TYPES = six.integer_types

ERROR_NOT_FOUND = 'ERROR_NOT_FOUND'
ACCESS_ERROR = 'ACCESS_ERROR'
USER_ACCESS_ERROR = 'user_access_error'
AUTHORIZATION_ERROR = 'authorization_error'
INVALID_TOKEN = 'invalid_token'
NO_AUTH_FOUND = 'NO_AUTH_FOUND'
APPLICATION_NOT_FOUND = 'APPLICATION_NOT_FOUND'
QUERY_LIMIT_EXCEEDED = 'QUERY_LIMIT_EXCEEDED'

"""
Наследование исключений:
Exception
└── BitrixApiException
    ├── BitrixApiError
    │   ├── ExpiredToken
    │   ├── BitrixTokenRefreshError
    │   ├── BitrixApiServerError
    │   ├── SnapiError
    │   └── BitrixApiErrorNotFound
    ├── BatchFailed
    │   └── BatchApiCallError
    │   └── JsonDecodeBatchFailed
    └── BaseRequestException
        ├── BitrixRequestException
        ├── BitrixOauthRefreshRequestException
        ├── BaseConnectionError
        │   ├── BitrixConnectionError (ConnectionToBitrixError)
        │   └── BitrixOauthRefreshConnectionError (BitrixOauthConnectionError)
        └── BaseTimeout
            ├── BitrixTimeout
            └── BitrixOauthRefreshTimeout
"""


class BitrixApiException(Exception):
    """
    Ошибка при работе с API Битрикс.
    """
    @property
    def friendly_error(self):
        """
        Текст ошибки, который можно отдавать конечному пользователю.
        """
        return 'Неизвестное исключение REST API Битрикс24.'

    @property
    def is_not_logic_error(self):
        return False


def get_bitrix_api_error(json_response, status_code, message=''):
    bitrix_api_error = BitrixApiError(has_resp='deprecated', json_response=json_response, status_code=status_code, message=message)
    if bitrix_api_error.is_not_found:
        return BitrixApiErrorNotFound(has_resp='deprecated', json_response=json_response, status_code=status_code, message=message)
    else:
        return bitrix_api_error


class BitrixApiError(BitrixApiException):
    """
    Ошибка при одиночном запросе к Битрикс.
    Обычно означает JSON-ответ от Битрикс с ошибкой.
    Бывают внутренние ошибки сервера Битрикс без JSON в ответе.
    Иногда формируем ошибку сами (не ответ Битрикс).
    """
    TOKEN_DEACTIVATED = 'token_deactivated'

    def __init__(self, has_resp, json_response, status_code, message, token=None):
        """
        :param has_resp: Не используется (ставить 'deprecated').
        :param json_response: JSON-ответ с ошибкой, если есть.
        :param status_code: HTTP-статус ответа с ошибкой.
        :param message: Укороченное пояснение.
        :param token: Токен, использовавшийся для запроса.
        """
        self.has_resp = has_resp
        self.json_response = json_response
        self.status_code = status_code
        self.message = message
        self.token = token

    def __str__(self):
        return f"{self.json_response}, {self.status_code}, {self.message}, token={self.token}"

    @property
    def error(self):
        if isinstance(self.json_response, dict):
            return self.json_response.get('error')

    @property
    def error_description(self):
        if isinstance(self.json_response, dict):
            return self.json_response.get('error_description')

    @property
    def friendly_error(self):
        if self.is_token_deactivated:
            return 'Токен Битрикс24 деактивирован в приложении.'
        if self.is_cant_refresh:
            return 'Не удалось обновить access-токен Битрикс24.'
        if self.is_unable_to_authorize_user:
            return 'Пользователь Битрикс24 не активен: уволен или заблокирован.'
        if self.is_user_cant_be_authorized_in_context:
            return 'Токен действителен, но связанный с ним пользователь не может быть авторизован в этом контексте.'
        if self.is_invalid_token:
            return 'Битрикс24 не смог сопоставить OAuth-токен с приложением.'
        if self.is_token_expired:
            return 'Access-токен Битрикс24 истёк, нужно обновить токен.'
        if self.is_user_access_error:
            return 'У пользователя нет доступа к приложению Битрикс24.'
        if self.is_access_error:
            return 'У токена нет доступа к запрошенному объекту или действию Битрикс24.'
        if self.is_access_denied_extended_plans:
            return 'Действие доступно только на расширенных тарифах Битрикс24.'
        if self.is_access_denied_no_rights_for_list:
            return 'У пользователя нет прав для просмотра и редактирования списка Битрикс24.'
        if self.is_access_denied:
            return 'Битрикс24 отказал в доступе к запрошенному действию.'
        if self.is_free_plan_error:
            return 'REST API доступен только на коммерческих тарифах Битрикс24.'
        if self.is_payment_required:
            return 'У портала Битрикс24 закончилась активная подписка.'
        if self.is_out_of_disc_space_error:
            return 'На портале Битрикс24 исчерпан выделенный дисковый ресурс.'
        if self.is_not_found:
            return 'Запрошенный объект Битрикс24 не найден.'
        if self.is_error_not_found:
            return 'Запрошенная сущность или тип не найдены в Битрикс24.'
        if self.is_method_not_found:
            return 'REST-метод не найден: проверьте имя метода, доступность модуля и тариф портала.'
        if self.is_no_auth_found:
            return 'Битрикс24 не распознал переданные данные авторизации.'
        if self.is_portal_deleted:
            return 'Портал Битрикс24 остановлен, удалён или его публичная часть недоступна.'
        if self.is_wrong_encoding:
            return 'Битрикс24 не смог корректно сформировать JSON-ответ из-за ошибки кодировки.'
        if self.is_application_not_found:
            return 'OAuth-приложение не найдено или неактивно на портале Битрикс24.'
        if self.is_application_not_installed:
            return 'Приложение удалено или не установлено на портале Битрикс24.'
        if self.is_connection_to_bitrix_error:
            return 'Не удалось подключиться к порталу Битрикс24.'
        if self.is_error_connecting_to_authorization_server:
            return 'Не удалось подключиться к серверу авторизации Битрикс24.'
        if self.is_connection_error:
            return 'Не удалось подключиться к серверу авторизации Битрикс24.'
        if self.is_license_check_failed:
            return 'Проверка лицензии портала Битрикс24 не пройдена.'
        if self.is_sphinx_connect_error:
            return 'Битрикс24 не смог подключиться к поисковому сервису Sphinx.'
        if self.is_mysql_query_error:
            return 'Внутренняя ошибка базы данных на стороне Битрикс24.'
        if self.is_bad_gateway:
            return 'Шлюз Битрикс24 вернул ошибку Bad Gateway.'
        if self.is_gateway_timeout:
            return 'Битрикс24 не ответил вовремя: шлюз вернул Gateway Timeout.'
        if self.is_operation_time_limit:
            return 'Метод заблокирован из-за превышения лимита времени выполнения операции.'
        if self.is_portal_blocked_by_license_scanner:
            return 'Портал Битрикс24 заблокирован проверкой лицензии.'
        if self.is_workflow_not_found:
            return 'Бизнес-процесс Битрикс24 не найден или уже завершён.'
        if self.is_batch_length_exceeded:
            return 'Превышен максимальный размер batch-запроса или количество операций в нём.'
        if self.is_invalid_argument_value:
            return 'В запросе передано недопустимое значение одного из параметров.'
        if self.is_no_client_credentials:
            return 'На портале Битрикс24 не настроены service_client_id/service_client_secret для REST.'
        if self.is_https_required:
            return 'Для вызова REST API Битрикс24 требуется HTTPS.'
        if self.is_invalid_request_credentials:
            return 'Битрикс24 не принял данные авторизации: проверьте access-токен, вебхук или параметры OAuth.'
        if self.is_user_not_authorized:
            return 'Пользователь не авторизован в сессии Битрикс24.'
        if self.is_access_denied_for_user_type:
            return 'Авторизация через сессию запрещена для этого типа пользователя Битрикс24.'
        if self.is_session_failed:
            return 'Проверка CSRF-токена сессии Битрикс24 не пройдена.'
        if self.is_application_overload_limit:
            return 'REST API Битрикс24 временно заблокирован из-за перегрузки приложения или вебхука.'
        if self.is_service_overload_limit:
            return 'REST API Битрикс24 временно заблокирован из-за общей перегрузки сервиса.'
        if self.is_subscription_required:
            return 'Входящий вебхук заблокирован из-за ограничений подписки Битрикс24.'
        if self.is_webhook_insufficient_scope:
            return 'Вебхуку не хватает прав для выполнения этого REST-метода.'
        if self.is_method_confirmation_waiting:
            return 'Вызов REST-метода ожидает подтверждения пользователем.'
        if self.is_rate_limit_exceeded:
            return 'Интеграция или вебхук временно заблокированы из-за превышения лимита запросов.'
        if self.is_method_confirmation_denied:
            return 'Пользователь отклонил подтверждение вызова REST-метода.'
        if self.is_intranet_user_required:
            return 'Метод доступен только внутренним пользователям портала Битрикс24.'
        if self.is_manifest_not_available:
            return 'Манифест приложения или REST-метода недоступен.'
        if self.is_batch_method_not_allowed:
            return 'Этот REST-метод нельзя вызывать внутри batch.'
        if self.is_sql_query_error:
            return 'Внутренняя SQL-ошибка на стороне Битрикс24.'
        if self.is_unexpected_answer:
            return 'Сервер Битрикс24 вернул неожиданный ответ.'
        if self.is_wrong_transport:
            return 'Запрошен неподдерживаемый формат ответа Битрикс24.'
        if self.is_wrong_handler_class:
            return 'Внутренняя ошибка Битрикс24: некорректный класс обработчика REST-метода.'
        if self.is_too_many_requests:
            return 'Превышен общий лимит интенсивности запросов к REST API Битрикс24.'
        if self.is_invalid_scope:
            return 'Запрошенные права превышают разрешения, доступные этому OAuth-гранту.'
        if self.is_refresh_token_parameter_missing:
            return 'OAuth-запрос неполный: отсутствует обязательный параметр refresh_token.'
        if self.is_wrong_auth_type:
            return 'Этот тип авторизации нельзя использовать для данного REST-метода.'
        if self.is_wrong_license:
            return 'Функция недоступна на текущем тарифе Битрикс24.'
        if self.is_error_core:
            return 'Внутренняя ошибка Битрикс24 при обработке REST-запроса.'
        if self.is_internal_server_error:
            return 'Внутренняя ошибка сервера Битрикс24.'
        if self.status_code is not None and self.is_status_gte_500:  # У batch-ошибки может не быть статус-кода.
            return 'Битрикс24 вернул серверную ошибку.'
        if self.is_insufficient_scope:
            return 'Токену не хватает прав для выполнения этого REST-метода.'
        if self.is_authorization_error:
            return 'Битрикс24 не смог авторизовать пользователя.'
        if self.is_access_denied_any:
            return 'Битрикс24 отказал в доступе к запрошенному действию.'
        if self.is_unauthorized_any:
            return 'Битрикс24 не авторизовал REST-запрос.'

        return 'Неизвестная ошибка REST API Битрикс24.'

    @property
    def is_not_logic_error(self):
        if any([
            self.is_internal_server_error,
            self.is_error_connecting_to_authorization_server,
            self.is_connection_to_bitrix_error,
            self.is_license_check_failed,
            self.is_no_auth_found,
            self.is_portal_deleted,
            self.is_free_plan_error,
            self.is_payment_required,
            self.is_wrong_encoding,
            self.is_authorization_error,
            self.is_out_of_disc_space_error,
            self.is_status_gte_500,
            self.is_application_not_found,
            self.is_application_not_installed,
            self.is_sphinx_connect_error,
            self.is_error_core,
            self.is_connection_error,
            self.is_cant_refresh,
            self.is_mysql_query_error,
            self.is_portal_blocked_by_license_scanner,
        ]):
            return True
        return False

    @property
    def is_error_core(self):
        """
        Пример: error='ERROR_CORE',
        error_description='Command has unprocessed exception: "OOM command not allowed when used memory > \'maxmemory\'.". Code: "0"',
        status_code=400
        """
        return self.error == 'ERROR_CORE'

    @property
    def is_token_deactivated(self):
        """
        Ошибка формируется нами, когда деактивируем токен.
        """
        return self.message == self.TOKEN_DEACTIVATED

    @property
    def is_invalid_token(self):
        """
        Неправильный токен. Скорее всего, не для того портала/приложения.
        Пример: error='invalid_token', error_description='Unable to get application by token', status_code=401
        """
        return self.error == INVALID_TOKEN

    @property
    def is_access_error(self):
        """
        У токена нет доступа.
        Пример: error='ACCESS_ERROR', error_description='You do not have access to the specified dialog', status_code=403
        """
        return self.error == ACCESS_ERROR

    @property
    def is_user_access_error(self):
        """
        У сотрудника нет доступа к приложению (настраивается администратором портала).
        Пример: error='user_access_error', error_description='The user does not have access to the application.', status_code=401
        """
        return self.error == USER_ACCESS_ERROR

    @property
    def is_authorization_error(self):
        """
        Ошибка авторизации. Может быть из-за увольнения/блокировки, может быть и по другим причинам.
        TODO: Разобраться с REST_OAUTH_ERROR_LOGOUT_BEFORE в \Bitrix\Rest\OAuth\Auth::onRestCheckAuth.
        Пример: error='authorization_error', error_description='Unable to authorize user'
        """
        return self.error == AUTHORIZATION_ERROR

    @property
    def is_unable_to_authorize_user(self):
        """
        Сотрудник, скорее всего, уволен или заблокирован.
        Но желательно перепроверять через user.get - возможно Битрикс что-то поменяет.
        Пример: error='authorization_error', error_description='Unable to authorize user'
        """
        return self.error_description == "Unable to authorize user"

    @property
    def is_user_cant_be_authorized_in_context(self):
        """
        Сотрудник удалён с коробки, не подтвердил регистрацию или с пустым LAST_ACTIVITY_DATE или LAST_LOGIN_DATE.
        При упрощённом протоколе OAuth (через iframe) - может не упасть, если не удалён пользователь.
        Код ядра: \Bitrix\Rest\OAuth\Auth::check -> !$accessChecker->canAuthorize()
        Желательно перепроверять через user.get - возможно Битрикс что-то поменяет.
        Пример: error='ACCESS_DENIED', error_description='Current user can't be authorized in this context'
        """
        return self.error_description == "Current user can't be authorized in this context"

    @property
    def is_cant_refresh(self):
        """
        Ошибка формируется нами, когда не удалось обновить протухший токен.
        """
        return self.message == 'cant_refresh'

    @property
    def is_free_plan_error(self):
        """
        Бесплатный тариф на портале (недоступен REST).
        """
        return self.error_description == "REST is available only on commercial plans."

    @property
    def is_payment_required(self):
        """
        Отсутствует или закончилась подписка портала на Маркетплейс (недоступен REST).
        Пример: error='PAYMENT_REQUIRED', error_description='Subscription has been ended', status_code=401
        """
        return self.error == 'PAYMENT_REQUIRED'

    @property
    def is_not_found(self):
        return self.error_description == "Not found" and self.status_code == 400

    @property
    def is_error_not_found(self):
        return self.error == ERROR_NOT_FOUND

    @property
    def is_internal_server_error(self):
        """
        Внутренняя ошибка сервера Битрикс.
        Пример: error='INTERNAL_SERVER_ERROR', error_description='Internal server error', status_code=500
        """
        return self.error == 'INTERNAL_SERVER_ERROR'

    @property
    def is_sphinx_connect_error(self):
        return isinstance(self.error_description, str) and "Sphinx connect error" in self.error_description and self.status_code == 400

    @property
    def is_connection_to_bitrix_error(self):
        """
        Deprecated.
        Ошибка формировалась нами в call_api_method через превращение ConnectionToBitrixError в BitrixApiError.
        Данное превращение убрано из-за нелогичности, теперь нужно перехватывать BitrixConnectionError.
        """
        return self.error == 'ConnectionToBitrixError'

    @property
    def is_connection_error(self):
        """
        Пример: error='CONNECTION_ERROR', error_description='Error connecting to authorization server', status_code=401
        """
        return self.error == 'CONNECTION_ERROR'

    @property
    def is_error_connecting_to_authorization_server(self):
        """
        Пример: error='CONNECTION_ERROR', error_description='Error connecting to authorization server', status_code=401
        """
        return self.error_description == "Error connecting to authorization server"

    @property
    def is_license_check_failed(self):
        """
        У портала проблемы с лицензией (облачным тарифом).
        Пример: error='verification_needed', error_description='License check failed.', status_code=401
        """
        return self.error_description == "License check failed."

    @property
    def is_insufficient_scope(self):
        """
        Не хватает разрешения (scope) у приложения.
        Пример: error='insufficient_scope',
        error_description='The request requires higher privileges than provided by the access token', status_code=401
        """
        return self.error == 'insufficient_scope'

    @property
    def is_method_not_found(self):
        """
        Нету такого REST-метода на портале. Часто возникает из-за ограничений тарифа.
        Пример: error='ERROR_METHOD_NOT_FOUND', error_description='Method not found!', status_code=404
        """
        return self.error == 'ERROR_METHOD_NOT_FOUND'

    @property
    def is_no_auth_found(self):
        """
        Случайная фигня от Битрикс, когда он сам заворачивает свои же токены.
        TODO: Объяснить более подробно с примером.
        """
        return self.error == NO_AUTH_FOUND

    @property
    def is_portal_deleted(self):
        """
        Означает, что публичная часть портала скрыта (не всегда значит, что удалён).
        """
        return self.error == 'PORTAL_DELETED'

    @property
    def is_wrong_encoding(self):
        return self.error == 'WRONG_ENCODING'

    @property
    def is_application_not_found(self):
        return self.error == APPLICATION_NOT_FOUND

    @property
    def is_application_not_installed(self):
        """
        Пример: error='ERROR_OAUTH', error_description='Application not installed', status_code=401
        """
        return self.error_description == 'Application not installed'

    @property
    def is_status_gte_500(self):
        return self.status_code >= 500

    @property
    def is_out_of_disc_space_error(self):
        """
        Пример: error='ERROR_OAUTH', error_description='Исчерпан выделенный дисковый ресурс.<br>', status_code=401
        """
        return self.error_description in [
            # Тут надо собрать description для этой ошибки на каждом языке
            'Вичерпано виділений дисковий ресурс.<br>',
            'Исчерпан выделенный дисковый ресурс.<br>',
            'Disk quota exceeded.<br>',
        ]

    @property
    def is_token_expired(self):
        """
        Протухший токен.
        Пример: error='expired_token',
        error_description='The access token provided has expired.', status_code=401
        """
        return self.error == 'expired_token'

    @property
    def is_access_denied_any(self):
        return self.error == 'ACCESS_DENIED'

    @property
    def is_access_denied(self):
        return self.is_access_denied_any and self.error_description == 'Access denied!'

    @property
    def is_access_denied_extended_plans(self):
        return self.is_access_denied_any and self.error_description == 'Access denied! Available only on extended plans'

    @property
    def is_access_denied_no_rights_for_list(self):
         return self.is_access_denied_any and self.error_description == 'Нет прав для просмотра и редактирования списка.'

    @property
    def is_bad_gateway(self):
        return str(self.error).casefold() == 'bad gateway'

    @property
    def is_gateway_timeout(self):
        return self.status_code == 504

    @property
    def is_unauthorized_any(self):
        return self.status_code == 401

    @property
    def is_operation_time_limit(self):
        return self.error == 'OPERATION_TIME_LIMIT'

    @property
    def is_mysql_query_error(self):
        return isinstance(self.error_description, str) and 'mysql query error' in self.error_description.lower()

    @property
    def is_portal_blocked_by_license_scanner(self):
        """
        Пример: error='PORTAL_BLOCKED_BY_LICENSE_SCANNER',
        error_description='Portal is blocked by the license scanner.'
        """
        return self.error == 'PORTAL_BLOCKED_BY_LICENSE_SCANNER'

    @property
    def is_workflow_not_found(self):
        """
        Запуск бизнес-процесса в b_bp_workflow_instance не найден (возможно, завершён).
        Пример: error='404', error_description='Бизнес-процесс не найден'
        """
        return self.error_description == "Бизнес-процесс не найден"

    @property
    def is_batch_length_exceeded(self):
        return self.error_description == 'Max batch length exceeded'

    @property
    def is_invalid_argument_value(self):
        return self.error_description == 'Invalid argument value provided'

    @property
    def is_no_client_credentials(self):
        return self.error_description == 'No client credentials'

    @property
    def is_https_required(self):
        return self.error_description == 'Https required'

    @property
    def is_invalid_request_credentials(self):
        return self.error_description == 'Invalid request credentials'

    @property
    def is_user_not_authorized(self):
        return self.error_description == 'User not authorized'

    @property
    def is_access_denied_for_user_type(self):
        return self.error_description == 'Access denied for this type of user'

    @property
    def is_session_failed(self):
        return self.error_description == 'Sessid check failed'

    @property
    def is_application_overload_limit(self):
        return self.error_description == 'REST API is blocked due to overload.'

    @property
    def is_service_overload_limit(self):
        return self.error_description == 'REST API is blocked due to overload'

    @property
    def is_subscription_required(self):
        return self.error_description == 'REST is available only by subscription.'

    @property
    def is_webhook_insufficient_scope(self):
        return self.error_description == 'The request requires higher privileges than provided by the webhook token'

    @property
    def is_method_confirmation_waiting(self):
        return self.error_description == 'Waiting for confirmation'

    @property
    def is_rate_limit_exceeded(self):
        return self.error_description == 'Rate limit exceeded. Too many requests in a given amount of time.'

    @property
    def is_method_confirmation_denied(self):
        return self.error_description == 'Method call denied'

    @property
    def is_intranet_user_required(self):
        return self.error_description == 'Method allowed only for intranet users'

    @property
    def is_manifest_not_available(self):
        return self.error_description == 'Manifest is not available'

    @property
    def is_batch_method_not_allowed(self):
        return self.error_description == 'Method is not allowed for batch usage'

    @property
    def is_sql_query_error(self):
        return self.error_description == 'SQL query error!'

    @property
    def is_unexpected_answer(self):
        return self.error_description in ('Server returned an unexpected response', 'Server returned an unexpected response.')

    @property
    def is_wrong_transport(self):
        return self.error_description == 'Wrong transport!'

    @property
    def is_wrong_handler_class(self):
        return self.error_description == 'Wrong handler class!'

    @property
    def is_too_many_requests(self):
        return self.error_description == 'Too many requests'

    @property
    def is_invalid_scope(self):
        return self.error_description == 'Given scope exceeds permissions associated with given grant'

    @property
    def is_refresh_token_parameter_missing(self):
        return self.error_description == 'No "refresh_token" parameter found'

    @property
    def is_wrong_auth_type(self):
        return bool(self.error_description and self.error_description.startswith(
            'Current authorization type is denied for this method'
        ))

    @property
    def is_wrong_license(self):
        return bool(self.error_description and self.error_description.startswith(
            'This feature is not enabled for the current license:'
        ))

    def dict(self):
        if isinstance(self.json_response, dict):
            error = self.json_response
        else:
            error = dict(error=self.json_response)
        error.setdefault('error_message', self.message)
        return error

    # def __str__(self):
    #     return "{} {}".format(self.status_code, self.get_response_text())
    #
    # def get_response_text(self):
    #     return getattr(self.response, 'text', str(self.response))

    def json_http_response(self, status=None):
        if status is None:
            new_status = None
            if isinstance(self.status_code, STRING_TYPES) and \
                    self.status_code.isdigit():
                new_status = int(self.status_code)
            elif isinstance(self.status_code, INTEGER_TYPES):
                new_status = self.status_code
            if new_status and 100 <= new_status <= 599:
                status = new_status
        status = status or 500
        json_error_response = JsonResponse(self.dict(), status=status)
        if status >= 500:
            # skip django reports for 5xx responses
            json_error_response._has_been_logged = True
        return json_error_response


class ExpiredToken(BitrixApiError):
    """
    Ошибка для обработки протухшего токена.
    """
    def __init__(self, status_code=401):
        # from collections import namedtuple
        # json_response = namedtuple('Response', ['text'], defaults=['expired_token'])()
        # это было сделано чтобы можно было обращаться json_response.text
        super().__init__(has_resp='deprecated', json_response={'error': 'expired_token'}, status_code=status_code, message='expired_token')


class BitrixTokenRefreshError(BitrixApiError):
    """
    Ошибка обновления токена Битрикс.
    """
    def __init__(self, has_resp, json_response, status_code, message='cant_refresh', token=None):
        super().__init__(has_resp, json_response, status_code, message, token)


class BitrixApiServerError(BitrixApiError):
    """
    Внутренняя ошибка сервера Битрикс.
    Обычно означает, что сервер вернул не JSON в ответе.
    """
    is_internal_server_error = True


class SnapiError(BitrixApiError):
    """
    Ошибка вызова Snapi-метода.
    Смотреть: bitrix_utils.BitrixUserToken.call_snapi_method.
    """


class BitrixApiErrorNotFound(BitrixApiError):
    """
    Ошибка BitrixApiError.is_not_found.
    TODO: Объяснить, почему сделана отдельным классом.
    """


class BatchFailed(BitrixApiException):
    """
    Ошибка batch-запроса.
    """
    def __init__(self, reason=None):
        self.reason = reason

    def __str__(self):
        return f"{self.reason}"


class BatchApiCallError(BatchFailed):
    """
    Сервер вернул JSON-ответ с ошибкой на batch-запрос.
    Через свойство реализована сборка BitrixApiError для использования свойства is_not_logic_error
    без дублирования условий в двух разных исключениях.
    """
    @property
    def status_code(self):
        """
        Статус запроса для сборки BitrixApiError.
        Пока получаем только, если reason - это Response.
        """
        if isinstance(self.reason, Response):
            return self.reason.status_code

    @property
    def json_response(self):
        """
        JSON запроса для сборки BitrixApiError.
        Пока получаем только, если reason - это Response.
        """
        response = self.reason
        if isinstance(self.reason, Response):
            try:
                response_json = response.json()
            except (ValueError, TypeError):
                response_json = None
            return response_json

    @property
    def bitrix_api_error(self):
        """
        Сборка BitrixApiError для использования is_not_logic_error.
        """
        return BitrixApiError(
            has_resp='deprecated',
            json_response=self.json_response,
            status_code=self.status_code,
            message='batch_api_call_error',
        )

    @property
    def friendly_error(self):
        return self.bitrix_api_error.friendly_error

    @property
    def is_not_logic_error(self):
        """
        Используется свойство из BitrixApiError.
        Немного костыльно, но пока так.
        """
        bitrix_api_error = self.bitrix_api_error
        if bitrix_api_error:
            return bitrix_api_error.is_not_logic_error
        return False


class JsonDecodeBatchFailed(BatchFailed):
    """
    Сервер вернул не JSON в ответе на batch-запрос.
    Обычно означает внутреннюю ошибку сервера Битрикс.
    """
    @property
    def is_not_logic_error(self):
        return True

    @property
    def friendly_error(self):
        return 'Битрикс24 вернул не JSON в ответе на batch-запрос.'


class BaseRequestException(BitrixApiException):
    """
    Ошибка выполнения запроса.
    В случае таких ошибок мы не получили никакого ответа от сервера.
    Соответствует исключению requests.RequestException.
    """
    def __init__(self, requests_exception):
        self.requests_exception = requests_exception

    @property
    def is_not_logic_error(self):
        return True

    @property
    def friendly_error(self):
        return 'Не удалось выполнить запрос к Битрикс24.'

    def __str__(self):
        return f"{self.requests_exception}"


class BitrixRequestException(BaseRequestException):
    """
    Ошибка выполнения запроса к порталу Bitrix.
    """


class BitrixOauthRefreshRequestException(BaseRequestException):
    """
    Ошибка выполнения запроса к серверу авторизации Bitrix при обновлении токена.
    """


class BaseConnectionError(BaseRequestException):
    """
    Ошибка соединения при запросе.
    Соответствует исключению requests.ConnectionError.
    """
    def __init__(self, requests_connection_error):
        super().__init__(requests_connection_error)
        self.requests_connection_error = requests_connection_error

    @property
    def is_not_logic_error(self):
        return True


class BitrixConnectionError(BaseConnectionError):
    """
    Ошибка соединения при запросе к порталу Битрикс.
    """
    @property
    def friendly_error(self):
        return 'Не удалось подключиться к порталу Битрикс24. Проверьте доступность портала и сетевое соединение.'


# Для обратной совместимости
ConnectionToBitrixError = BitrixConnectionError


class BitrixOauthRefreshConnectionError(BaseConnectionError):
    """
    Ошибка соединения при запросе к серверу авторизации Битрикс при обновлении токена.
    """
    @property
    def friendly_error(self):
        return 'Не удалось подключиться к серверу авторизации Битрикс24 при обновлении токена.'


# Для обратной совместимости
BitrixOauthConnectionError = BitrixOauthRefreshConnectionError


class BaseTimeout(BaseRequestException):
    """
    Таймаут при запросе.
    Соответствует исключению requests.Timeout.
    """
    def __init__(self, requests_timeout, timeout):
        super().__init__(requests_timeout)
        self.request_timeout = requests_timeout
        self.timeout = timeout

    @property
    def is_not_logic_error(self):
        return True


class BitrixTimeout(BaseTimeout):
    """
    Таймаут при запросе к порталу Битрикс.
    """
    @property
    def friendly_error(self):
        return 'Портал Битрикс24 не ответил за отведённое время.'


class BitrixOauthRefreshTimeout(BaseTimeout):
    """
    Таймаут при запросе к серверу авторизации Битрикс при обновлении токена.
    """
    @property
    def friendly_error(self):
        return 'Сервер авторизации Битрикс24 не ответил за отведённое время при обновлении токена.'

