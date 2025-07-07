from django.http import JsonResponse
import six

STRING_TYPES = six.string_types
INTEGER_TYPES = six.integer_types

ERROR_NOT_FOUND = 'ERROR_NOT_FOUND'
USER_ACCESS_ERROR = 'user_access_error'
AUTHORIZATION_ERROR = 'authorization_error'
INVALID_TOKEN = 'invalid_token'
NO_AUTH_FOUND = 'NO_AUTH_FOUND'
APPLICATION_NOT_FOUND = 'APPLICATION_NOT_FOUND'
QUERY_LIMIT_EXCEEDED = 'QUERY_LIMIT_EXCEEDED'


class BitrixApiException(Exception):
    """
    Ошибки от АПИ
    """
    pass


# Статус коды добавленные
# 600
# raise BitrixApiError(has_resp='deprecated', json_response={'error': 'ConnectionToBitrixError'}, status_code=600, message='')
# 601
# raise BitrixApiError(has_resp='deprecated', json_response={"error": "json ValueError"}, status_code=601, message='')

def get_bitrix_api_error(json_response, status_code, message=''):
    bitrix_api_error = BitrixApiError(has_resp='deprecated', json_response=json_response, status_code=status_code, message=message)
    if bitrix_api_error.is_not_found:
        return BitrixApiErrorNotFound(has_resp='deprecated', json_response=json_response, status_code=status_code, message=message)
    else:
        return bitrix_api_error


class BitrixApiError(BitrixApiException):
    TOKEN_DEACTIVATED = 'token_deactivated'

    def __init__(self, has_resp, json_response, status_code, message, refresh_error=None):
        # :has_resp - has response похоже на атавизм, не нашел применения достойного в коде УДАЛИТЬ?
        # :json_response - используется как минимум для анализа, что же там в ошибке было.
        # :status_code - http статус код ответа
        # message - укороченное пояснение ошибке не через json_response
        # refresh_error - пок тоже не понятно как применяется УДАЛИТЬ?

        # В integration_utils раньше применялись
        # raise BitrixApiError(401, dict(error='expired_token'))
        # Нужно переделать на
        # raise BitrixApiError(has_resp='deprecated', json_response=dict(error='expired_token'), status_code=401, message='expired_token')

        super(BitrixApiError, self).__init__(dict(
            has_resp=has_resp,
            json_response=json_response,
            status_code=status_code,
            message=message,
            refresh_error=refresh_error,
        ))
        self.has_resp = has_resp
        self.json_response = json_response
        self.status_code = status_code
        self.message = message
        self.refresh_error = refresh_error

    @property
    def error(self):  # 'error' из json-ответа
        if isinstance(self.json_response, dict):
            return self.json_response.get('error')

    @property
    def error_description(self):  # 'error_description' из json-ответа
        if isinstance(self.json_response, dict):
            return self.json_response.get('error_description')

    @property
    def is_token_deactivated(self):
        return self.message == 'token_deactivated'

    @property
    def is_invalid_token(self):
        return self.error == "invalid_token"

    @property
    def is_user_access_error(self):
        return self.error == "user_access_error"

    @property
    def is_authorization_error(self):
        return self.error == 'authorization_error'

    @property
    def is_cant_refresh(self):
        return self.error == 'expired_token' and self.message == 'cant_refresh'

    @property
    def is_free_plan_error(self):
        return self.error_description == "REST is available only on commercial plans."

    @property
    def is_not_found(self):
        return self.error_description == 'Not found' and self.status_code == 400

    @property
    def is_internal_server_error(self):
        # {'message': 'api_error', 'status_code': 500, 'refresh_error': None,
        #  'json_response': {'error_description': 'Internal server error',
        #                    'error': 'INTERNAL_SERVER_ERROR'}, 'has_resp': False}
        return self.error == "INTERNAL_SERVER_ERROR"

    @property
    def is_connection_to_bitrix_error(self):
        # {'refresh_error': None, 'message': 'ConnectionToBitrixError', 'has_resp': False,
        #  'json_response': {'error': 'ConnectionToBitrixError'}, 'status_code': 600}
        return self.error == "ConnectionToBitrixError"

    @property
    def is_error_connecting_to_authorization_server(self):
        # {'refresh_error': None, 'message': 'api_error',
        #  'json_response': {'error_description': 'Error connecting to authorization server',
        #                    'error': 'CONNECTION_ERROR'},
        #  'has_resp': False, 'status_code': 401}
        return self.error_description == "Error connecting to authorization server"

    @property
    def is_license_check_failed(self):
        # {'refresh_error': None, 'status_code': 401, 'message': 'api_error', 'json_response': {'error': 'verification_needed', 'error_description': 'License check failed.'}
        return self.error_description == "License check failed."

    @property
    def is_insufficient_scope(self):
        # Допустим нет права crm, а мы пробуем выполнить crm.lead.get
        return self.error == 'insufficient_scope'

    @property
    def is_no_auth_found(self):
        # Случайная фигня от Битрикс, когда он сам заворачивает свои же токены
        return self.error == 'NO_AUTH_FOUND'

    @property
    def is_portal_deleted(self):
        return self.error == 'PORTAL_DELETED'

    @property
    def is_wrong_encoding(self):
        return self.error == 'WRONG_ENCODING'

    @property
    def is_application_not_found(self):
        return self.error == 'APPLICATION_NOT_FOUND'

    @property
    def is_status_gte_500(self):
        return self.status_code >= 500

    @property
    def is_out_of_disc_space_error(self):
        return self.error == 'ACCESS_DENIED' and self.error_description in [
            # Тут надо собрать description для этой ошибки на каждом языке
            'Вичерпано виділений дисковий ресурс.<br>',
            'Исчерпан выделенный дисковый ресурс.<br>'
        ]

    @property
    def is_token_expired(self):
        # {'has_resp': True, 'json_response': {'error': 'expired_token', 'error_description': 'The access token provided has expired.'},
        # 'status_code': 401, 'message': 'cant_refresh', 'refresh_error': None}
        return self.error_description == 'The access token provided has expired.'

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
    # Наследуется от BitrixApiError, чтобы отлавливать одним исключением все ошибки АПИ.
    # Возможно, нужно наследовать от BitrixApiException.
    # TODO ошибки еще надо в порядок приводить

    def __init__(self, status_code=401):
        # from collections import namedtuple
        # json_response = namedtuple('Response', ['text'], defaults=['expired_token'])()
        # это было сделано чтобы можно было обращаться json_response.text
        super().__init__(has_resp=False, json_response={"error": "expired_token"}, status_code=status_code, message='expired_token', refresh_error=None)


class ConnectionToBitrixError(BitrixApiException):
    pass


class BatchApiCallError(BitrixApiException):
    def __init__(self, reason=None):
        self.reason = reason


class BatchFailed(BitrixApiException):
    def __init__(self, reason=None):
        self.reason = reason


class BitrixTokenRefreshError(BitrixApiError):
    pass


class BitrixApiServerError(BitrixApiError):
    is_internal_server_error = True


class SnapiError(BitrixApiError):
    pass


class JsonDecodeBatchFailed(BatchFailed):
    pass


class BaseTimeout(BitrixApiException):
    def __init__(self, requests_timeout, timeout):
        self.request_timeout = requests_timeout
        self.timeout = timeout

    def __repr__(self):
        rv = '<BitrixTimeout {!s}>'.format(self)
        return rv


class BitrixTimeout(BaseTimeout):
    def __str__(self):
        return '[{self.timeout} sec.] ' 'requests_timeout={self.request_timeout!r} ' 'request={self.request_timeout.request!r}'.format(self=self)


class BitrixOauthRefreshTimeout(BaseTimeout):
    def __str__(self):
        return 'oauth.bitrix.info - timeout {self.timeout} sec.'.format(self=self)


class BitrixApiErrorNotFound(BitrixApiError):
    # Ошибка когда не найдена Компания, или Контакт, или Лид или тп.
    pass
