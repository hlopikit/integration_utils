# -*- coding: UTF-8 -*-
from typing import Optional, Any, Union, Dict, Generator

from django.conf import settings

from integration_utils.bitrix24.exceptions import ExpiredToken, get_bitrix_api_error, BitrixApiServerError
from integration_utils.bitrix24.functions.api_call import api_call, api_call_v3
from integration_utils.bitrix24.functions.call_list_method import call_list_method
from integration_utils.retry_utils import RetryDecorator


class BaseBitrixToken:
    DEFAULT_TIMEOUT = getattr(settings, 'BITRIX_RESTAPI_DEFAULT_TIMEOUT', 10)
    RetrySettings = RetryDecorator

    domain = NotImplemented
    auth_token = NotImplemented
    web_hook_auth = NotImplemented

    def get_auth(self):
        return (self.web_hook_auth or self.auth_token), bool(self.web_hook_auth)

    def call_api_method(
            self,
            api_method: str,
            params: Optional[Dict[str, Any]] = None,
            timeout: Optional[int] = DEFAULT_TIMEOUT,
            retry_settings: Optional[RetryDecorator] = None,
    ) -> dict:
        def _call_method() -> dict:
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

        if retry_settings:
            _call_method = retry_settings(_call_method)

        return _call_method()

    call_api_method_v2 = call_api_method

    def call_api_method_v3(
            self,
            api_method: str,
            params: Optional[Dict[str, Any]] = None,
            timeout: Optional[int] = DEFAULT_TIMEOUT,
            retry_settings: Optional[RetryDecorator] = None,
    ) -> dict:
        """
        Метод для взаимодействия с REST API 3.0 Битрикс24.
        В случае ошибки - кидаем исключение.
        :param api_method: вызываемый REST-метод.
        :param params: параметры REST-метода.
        :param timeout: время таймаута в секундах для requests.
        :param retry_settings: настройки повторных попыток REST-вызова.
        :raise ValueError: Неправильное значение аргумента.
        :raise BitrixApiException: Ошибка при работе с API Битрикс.
        """
        def _call_method() -> dict:
            return api_call_v3(
                domain=self.domain,
                api_method=api_method,
                auth_token=self.auth_token,
                web_hook_auth=self.web_hook_auth,
                params=params,
                timeout=timeout,
            )

        if retry_settings:
            _call_method = retry_settings(_call_method)

        return _call_method()

    call_method = call_api_method_v3

    def batch_api_call(
            self,
            methods: Union[list, dict],
            timeout: Optional[int] = DEFAULT_TIMEOUT,
            chunk_size: int = 50,
            halt: int = 0,
            log_prefix: str = '',
            refresh: bool = True,
            retry_settings: Optional[RetryDecorator] = None,
    ) -> Any:
        """:rtype: bitrix_utils.bitrix_auth.functions.batch_api_call3.BatchResultDict
        """

        def _call_method() -> Any:
            from .functions.batch_api_call import batch_api_call
            # TODO: Поправить типизацию bitrix_user_token (через Protocol?)
            return batch_api_call(
                methods=methods,
                bitrix_user_token=self,
                timeout=timeout,
                chunk_size=chunk_size,
                halt=halt,
                log_prefix=log_prefix,
                refresh=refresh,
            )

        if retry_settings:
            _call_method = retry_settings(_call_method)

        return _call_method()

    batch_api_call_v3 = batch_api_call

    def call_list_fast(
        self,
        method: str,
        params: Dict[str, Any] = None,
        descending=False,
        log_prefix='',
        timeout: Optional[int] = DEFAULT_TIMEOUT,
        limit: Optional[int] = None,
        batch_size=50,
        retry_settings: Optional[RetryDecorator] = None,
    ) -> Generator[Dict, None, None]:
        """Списочный запрос с параметром ?start=-1
        см. описание bitrix_utils.bitrix_auth.functions.call_list_fast.call_list_fast

        Если происходит KeyError, надо добавить описание метода
        в справочники METHOD_TO_* в bitrix_utils.bitrix_auth.functions.call_list_fast
        """
        from .functions.call_list_fast import call_list_fast
        # TODO: Поправить типизацию tok (через Protocol?)
        return call_list_fast(
            tok=self,
            method=method,
            params=params,
            descending=descending,
            limit=limit,
            batch_size=batch_size,
            timeout=timeout,
            log_prefix=log_prefix,
            retry_settings=retry_settings,
        )

    def call_list_method(
            self,
            method,  # type: str
            fields=None,  # type: Optional[dict]
            limit=None,  # type: Optional[int]
            return_total=False,  # type: bool
            allowable_error=None,  # type: Optional[int]
            timeout=DEFAULT_TIMEOUT,  # type: Optional[int]
            force_total=None,  # type: Optional[int]  # TODO: Убрать когда-нибудь
            log_prefix='',  # type: str
            batch_size=50,  # type: int
            retry_settings=None,  # type: Optional[RetryDecorator]
    ):  # type: (...) -> Union[list, dict]
        return call_list_method(
            bx_token=self,
            method=method,
            fields=fields,
            limit=limit,
            return_total=return_total,
            force_total=force_total,
            allowable_error=allowable_error,
            timeout=timeout,
            log_prefix=log_prefix,
            batch_size=batch_size,
            retry_settings=retry_settings,
            v=2,
        )

    call_list_method_v2 = call_list_method


class BitrixToken(BaseBitrixToken):
    def __init__(self, domain, auth_token=None, web_hook_auth=None):
        self.domain = domain
        self.auth_token = auth_token
        self.web_hook_auth = web_hook_auth
