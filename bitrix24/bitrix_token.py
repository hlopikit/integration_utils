# -*- coding: UTF-8 -*-
from typing import Optional, Iterable, Any, Union

import requests
from django.conf import settings

from integration_utils.bitrix24.exceptions import ConnectionToBitrixError, BitrixTimeout, BitrixApiServerError, BitrixApiError, ExpiredToken, get_bitrix_api_error
from integration_utils.bitrix24.functions.api_call import api_call
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

        try:
            response = api_call(
                domain=self.domain,
                api_method=api_method,
                auth_token=auth,
                webhook=webhook,
                params=params,
                timeout=timeout,
            )
        except ConnectionToBitrixError:
            # fixme: BitrixApiError явно не ожидает, что туда передадут словарь
            #raise BitrixApiError(600, {'error': 'ConnectionToBitrixError'})
            raise BitrixApiError(has_resp='deprecated', json_response={'error': 'ConnectionToBitrixError'}, status_code=600, message='')

        # Пробуем раскодировать json
        try:
            json_response = response.json()
        except ValueError:
            #raise BitrixApiError(600, response)
            raise BitrixApiError(has_resp='deprecated', json_response={"error": "json ValueError"}, status_code=601, message='')

        if response.status_code in [200, 201] and not json_response.get('error'):
            return json_response

        if response.status_code == 401 and json_response['error'] == 'expired_token':
            raise ExpiredToken

        #raise BitrixApiError(response.status_code, response)
        raise get_bitrix_api_error(json_response=json_response, status_code=response.status_code, message='')

    call_api_method_v2 = call_api_method

    def call_api_method_v3(self, api_method: str, params: dict = None, timeout: int = DEFAULT_TIMEOUT):
        """
        Метод для взаимодействия с REST API 3.0 Битрикс24.
        В случае ошибки - кидаем исключение.

        :raises ConnectionToBitrixError (requests.ConnectionError/SSLError)
        :raises BitrixTimeout (requests.Timeout)
        :raises BitrixApiServerError (ответ не является JSON)
        :raises BitrixApiError (JSON-ответ содержит "error")
        """
        auth, webhook = self.get_auth()

        if params is None:
            payload = {}
        elif isinstance(params, dict):
            payload = dict(params)
        else:
            raise TypeError(f"params must be dict or None, got {type(params)!r}")

        hook_key = ""
        if webhook:
            hook_key = f"{auth}/"
        else:
            payload["auth"] = auth

        url = f'https://{self.domain}/rest/api/{hook_key}{api_method}'

        try:
            response = requests.post(
                url,
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                auth=getattr(settings, 'B24_HTTP_BASIC_AUTH', None),
                timeout=timeout,
                allow_redirects=False,
                verify=getattr(settings, 'B24API_IGNORE_SSL_VERIFICATION', True),
            )
        except (requests.ConnectionError, requests.exceptions.SSLError) as e:
            raise ConnectionToBitrixError(requests_connection_error=e)
        except requests.Timeout as e:
            raise BitrixTimeout(requests_timeout=e, timeout=timeout)

        status_code = response.status_code
        message = response.text

        try:
            json_response = response.json()
        except ValueError:
            raise BitrixApiServerError(has_resp='deprecated', json_response=None, status_code=status_code, message=message, token=self)

        if json_response.get('error'):
            raise BitrixApiError(has_resp='deprecated', json_response=json_response, status_code=status_code, message=message, token=self)

        return json_response

    def batch_api_call(self, methods, timeout=DEFAULT_TIMEOUT, chunk_size=50, halt=0, log_prefix=''):
        """:rtype: bitrix_utils.bitrix_auth.functions.batch_api_call3.BatchResultDict
        """
        from .functions.batch_api_call import _batch_api_call
        return _batch_api_call(methods=methods,
                               bitrix_user_token=self,
                               function_calling_from_bitrix_user_token_think_before_use=True,
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
