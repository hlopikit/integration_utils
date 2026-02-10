# -*- coding: UTF-8 -*-
from typing import Optional, Iterable, Any, Union

from django.conf import settings

from integration_utils.bitrix24.exceptions import ExpiredToken, get_bitrix_api_error, BitrixApiServerError
from integration_utils.bitrix24.functions.api_call import api_call, api_call_v3
from integration_utils.bitrix24.functions.call_list_method import call_list_method


class BaseBitrixToken:
    DEFAULT_TIMEOUT = getattr(settings, 'BITRIX_RESTAPI_DEFAULT_TIMEOUT', 10)

    domain = NotImplemented
    auth_token = NotImplemented
    web_hook_auth = NotImplemented

    def get_auth(self):
        return (self.web_hook_auth or self.auth_token), bool(self.web_hook_auth)

    def call_api_method(self, api_method, params=None, timeout=DEFAULT_TIMEOUT):
        auth, webhook = self.get_auth()
        response = api_call(
            domain=self.domain,
            api_method=api_method,
            auth_token=auth,
            webhook=webhook,
            params=params,
            timeout=timeout,
        )

        status_code = response.status_code
        message = response.text

        # Пробуем раскодировать json
        try:
            json_response = response.json()
        except ValueError as e:
            # Ранее здесь был BitrixApiError("error": "json ValueError", status_code=601)
            raise BitrixApiServerError(has_resp='deprecated', json_response=None, status_code=status_code, message=message) from e

        if status_code in [200, 201] and not json_response.get('error'):
            return json_response

        if status_code == 401 and json_response['error'] == 'expired_token':
            raise ExpiredToken

        #raise BitrixApiError(response.status_code, response)
        raise get_bitrix_api_error(json_response=json_response, status_code=response.status_code, message=message)

    call_api_method_v2 = call_api_method

    def call_api_method_v3(self, api_method: str, params: dict = None, timeout: int = DEFAULT_TIMEOUT):
        """
        Метод для взаимодействия с REST API 3.0 Битрикс24.
        В случае ошибки - кидаем исключение.

        :raises ValueError: Неправильное значение аргумента.
        :raises ConnectionToBitrixError: requests.ConnectionError/SSLError.
        :raises BitrixTimeout: requests.Timeout.
        :raises BitrixApiServerError: Ответ не является JSON.
        :raises BitrixApiError: JSON-ответ содержит "error".
        """
        return api_call_v3(
            domain=self.domain, api_method=api_method, auth_token=self.auth_token,
            web_hook_auth=self.web_hook_auth, params=params, timeout=timeout,
        )

    call_method = call_api_method_v3

    def batch_api_call(self, methods, timeout=DEFAULT_TIMEOUT, chunk_size=50, halt=0, log_prefix=''):
        """:rtype: bitrix_utils.bitrix_auth.functions.batch_api_call3.BatchResultDict
        """
        from .functions.batch_api_call import _batch_api_call
        return _batch_api_call(methods=methods,
                               bitrix_user_token=self,
                               timeout=timeout,
                               chunk_size=chunk_size,
                               halt=halt,
                               log_prefix=log_prefix)

    batch_api_call_v3 = batch_api_call

    def call_list_fast(
            self,
            method,  # type: str
            params=None,  # type: Optional[dict]
            descending=False,  # type: bool
            timeout=DEFAULT_TIMEOUT,  # type: Optional[int]
            log_prefix='',  # type: str
            limit=None,  # type: Optional[int]
            batch_size=50,  # type: int
    ):
        # type: (...) -> Iterable[Any]
        """Списочный запрос с параметром ?start=-1
        см. описание bitrix_utils.bitrix_auth.functions.call_list_fast.call_list_fast

        Если происходит KeyError, надо добавить описание метода
        в справочники METHOD_TO_* в bitrix_utils.bitrix_auth.functions.call_list_fast
        """
        from .functions.call_list_fast import call_list_fast
        return call_list_fast(self, method, params, descending=descending,
                              limit=limit, batch_size=batch_size,
                              timeout=timeout, log_prefix=log_prefix)

    def call_list_method(
            self,
            method,  # type: str
            fields=None,  # type: Optional[dict]
            limit=None,  # type: Optional[int]
            allowable_error=None,  # type: Optional[int]
            timeout=DEFAULT_TIMEOUT,  # type: Optional[int]
            force_total=None,  # type: Optional[int]  # TODO: Убрать когда-нибудь
            log_prefix='',  # type: str
            batch_size=50,  # type: int
    ):  # type: (...) -> Union[list, dict]
        result = call_list_method(self, method, fields=fields,
                                       limit=limit,
                                       force_total=force_total,
                                       allowable_error=allowable_error,
                                       timeout=timeout,
                                       log_prefix=log_prefix,
                                       batch_size=batch_size,
                                       v=2)
        return result

    call_list_method_v2 = call_list_method


class BitrixToken(BaseBitrixToken):
    def __init__(self, domain, auth_token=None, web_hook_auth=None):
        self.domain = domain
        self.auth_token = auth_token
        self.web_hook_auth = web_hook_auth
