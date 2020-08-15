# -*- coding: UTF-8 -*-

import hashlib
import logging
import six
import sys
import time
import traceback
from datetime import datetime

import requests
from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.db import models
from django.http import JsonResponse
from django.utils import timezone

from bitrix_utils.bitrix_auth.functions.call_list_method import call_list_method, CallListException
from integration_utils.bitrix24.exceptions import BitrixApiError, BitrixTimeout
from integration_utils.bitrix24.functions.api_call import api_call, ConnectionToBitrixError

if False:
    from typing import Optional, Sequence, Iterable, Any



def refresh_all():
    return BitrixUserToken.refresh_all()




class BitrixUserToken(models.Model):
    DEFAULT_TIMEOUT=10

    EXPIRED_TOKEN = 2
    INVALID_GRANT = 3
    NOT_INSTALLED = 4
    PAYMENT_REQUIRED = 5
    PORTAL_DELETED = 10
    ERROR_CORE = 11
    ERROR_OAUTH = 12
    ERROR_403_or_404 = 13
    NO_AUTH_FOUND = 14
    AUTHORIZATION_ERROR = 15
    ACCESS_DENIED = 16
    APPLICATION_NOT_FOUND = 17

    REFRESH_ERRORS = (
        (0, 'Нет ошибки'),
        (1, 'Не установлен портал (Wrong client)'),
        (EXPIRED_TOKEN, 'Устарел ключ совсем (Expired token)'),
        # бывает если ключи прилжения неправильные и "ВОЗМОЖНО" когда уже совсем протух токен
        (INVALID_GRANT, 'Инвалид грант (Invalid grant)'),
        (NOT_INSTALLED, 'Не установлен портал (NOT_INSTALLED)'),
        (PAYMENT_REQUIRED, 'Не оплачено (PAYMENT_REQUIRED)'),
        (6, 'Домен отключен или не существует'),
        (8, 'ошибка >= 500 '),
        (9, 'Надо разобраться (Unknown Error)'),
        (PORTAL_DELETED, 'PORTAL_DELETED'),
        (ERROR_CORE, 'ERROR_CORE'),
        (ERROR_OAUTH, 'ERROR_OAUTH'),
        (ERROR_403_or_404, 'ERROR_403_or_404'),
        (NO_AUTH_FOUND, 'NO_AUTH_FOUND'),
        (AUTHORIZATION_ERROR, 'AUTHORIZATION_ERROR'),
        (ACCESS_DENIED, 'ACCESS_DENIED'),
        (APPLICATION_NOT_FOUND, 'APPLICATION_NOT_FOUND'),
    )

    AUTH_COOKIE_MAX_AGE = None   # as long as the client’s browser session
    domain = settings.APP_SETTINGS.portal_domain
    web_hook_auth = None
    application = None

    user = models.OneToOneField('BitrixUser', related_name='bitrix_user_token', on_delete=models.CASCADE)

    auth_token = models.CharField(max_length=70)
    refresh_token = models.CharField(max_length=70, default='', blank=True)
    auth_token_date = models.DateTimeField()
    app_sid = models.CharField(max_length=70, blank=True)

    is_active = models.BooleanField(default=True)
    refresh_error = models.PositiveSmallIntegerField(default=0, choices=REFRESH_ERRORS)

    def __init__(self, *args, **kwargs):
        # 1) Можут в БД лежать уже готовые токены и тогда просто их используем
        # 2) Если надо на лету делать токены для вызовов методов АПИ, то
        # BitrixUserToken(auth_token='65c09d5d001c767d002443c00000000100000301144')
        super().__init__(*args, **kwargs)


    def signed_pk(self):
        #Пара из id токена и подписи, проверяем подпись при запросах
        assert self.pk
        from django.core.signing import TimestampSigner
        signer = TimestampSigner(key=settings.APP_SETTINGS.secret_key)
        return signer.sign(self.pk)

    @classmethod
    def get_by_signed_pk(cls, signed_pk):
        from django.core.signing import TimestampSigner
        signer = TimestampSigner(key=settings.APP_SETTINGS.secret_key)
        pk = signer.unsign(signed_pk)
        return cls.objects.get(pk=pk)


    def get_auth_key(self):
        # Ключ по которому мы можем определить можно ли воспользоваться токеном
        return hashlib.md5('{}_token_{}'.format(self.pk, settings.APP_SETTINGS.salt).encode()).hexdigest()

    @classmethod
    def get_by_token(cls, token):
        # Используется в декораторе bitrix_user_required для пользователиских АПИ запросов из приложений
        pk = cls.check_token(token)
        if pk:
            return cls.objects.get(pk=pk)

    @classmethod
    def check_token(cls, token):
        pk, token = token.split('::')
        # except (AttributeError, ValueError):
        #     return
        if token == cls.get_auth_token(pk):
            return pk

    def refresh(self, timeout=60):
        """
        Если успешно обновился токен, то возвращаем True
        Если что-то пошло не так то False

        :param timeout: таймаут запроса
        """
        if not self.pk:
            # Динамический токен
            raise BitrixApiError(401, dict(error='expired_token'))

        params = {
            'grant_type': 'refresh_token',
            'client_id': settings.APP_SETTINGS.application_bitrix_client_id,
            'client_secret': settings.APP_SETTINGS.application_bitrix_client_secret,
            'refresh_token': self.refresh_token,
        }
        params = '&'.join(['%s=%s' % (k, v) for k, v in params.items()])
        url = 'https://oauth.bitrix.info/oauth/token/?{}'.format(params)
        # url = 'https://{}/oauth/token/?{}'.format(self.user.portal.domain, params)
        try:
            response = requests.get(url, timeout=timeout)
        except requests.Timeout as e:
            raise BitrixTimeout(requests_timeout=e, timeout=timeout)


        if response.status_code >= 500:
            return False

        try:
            response_json = response.json()
        except (ValueError, TypeError):
            if response.status_code >= 403 and "portal404" in response.content:
                self.refresh_error = 6
                self.is_active = False
                self.save()
                return False

            return False

        if response_json.get('error'):
            if response_json.get('error') == u'invalid_grant':
                self.refresh_error = 3
            elif response_json.get('error') == u'wrong_client':
                self.refresh_error = 1
            elif response_json.get('error') == u'expired_token':
                self.refresh_error = 2
            elif response_json.get('error') == u'NOT_INSTALLED':
                self.refresh_error = 4
            elif response_json.get('error') == u'PAYMENT_REQUIRED':
                self.refresh_error = 5
            else:
                self.refresh_error = 9
            self.is_active = False
            self.save()
            return False
        else:
            self.refresh_error = 0

        self.auth_token = response_json.get('access_token')
        self.refresh_token = response_json.get('refresh_token')
        self.auth_token_date = timezone.now()
        self.is_active = True
        self.save()

        return True


    def call_api_method(self, api_method, params=None, timeout=DEFAULT_TIMEOUT):

        try:
            response = api_call(
                api_method=api_method,
                auth_token=self.auth_token,
                params=params,
                timeout=timeout,
            )
        except ConnectionToBitrixError:
            raise BitrixApiError(600, {'error': 'ConnectionToBitrixError'})

        # Пробуем раскодировать json
        try:
            json_response = response.json()
        except ValueError:
            raise BitrixApiError(600, response)

        if response.status_code in [200, 201]:
            # Нормальные ответы
            if json_response.get('error'):
                raise BitrixApiError(response.status_code, response)
            else:
                return json_response

        elif response.status_code in [500, 502, 504]:
          raise BitrixApiError(False, json_response, response.status_code, "api_error")
        else:
            if response.status_code == 401 and json_response['error'] == 'expired_token':
                # Ветка обновления Токена
                success = self.refresh(timeout=timeout)
                if success:
                    # Если обновление токена прошло успешно, повторить запрос
                    return self.call_api_method(api_method, params, timeout=timeout)
                else:
                    raise BitrixApiError(response.status_code, response)

            raise BitrixApiError(response.status_code, response)


    def deactivate_token(self, refresh_error):
        if self.pk:
            self.is_active = False
            self.refresh_error = refresh_error
            self.save(force_update=True)


    def batch_api_call(self, methods, timeout=DEFAULT_TIMEOUT, v=2, chunk_size=50, log_prefix=''):
        """см. ..functions.batch_api_call[v]
        """
        if v != 3:
            ilogger.error('batch_api_call_v2_deprecation', 'batch_api_call_v2_deprecation')

        if v == 3:
            return self.batch_api_call_v3(methods=methods, timeout=timeout,
                                          chunk_size=chunk_size, log_prefix=log_prefix)
        elif chunk_size != 50:
            raise RuntimeError('chunk_size only supported with v=3')

        return batch_api_call2(methods=methods, bitrix_user_token=self, timeout=timeout)

    def batch_api_call_v3(self, methods, timeout=DEFAULT_TIMEOUT,
                          chunk_size=50, halt=0, log_prefix=''):
        """:rtype: bitrix_utils.bitrix_auth.functions.batch_api_call3.BatchResultDict
        """
        from ..functions.batch_api_call3 import _batch_api_call3, BatchApiCallError
        try:
            return _batch_api_call3(methods=methods,
                                    bitrix_user_token=self,
                                    function_calling_from_bitrix_user_token_think_before_use=True,
                                    timeout=timeout,
                                    chunk_size=chunk_size,
                                    halt=halt,
                                    log_prefix=log_prefix)
        except BatchApiCallError as e:
            self.check_deactivate_errors(e.reason)
            raise e

    def call_list_method(
            self,
            method,  # type: str
            fields=None,  # type: Optional[dict]
            limit=None,  # type: Optional[int]
            allowable_error=None,  # type: Optional[int]
            timeout=DEFAULT_TIMEOUT,  # type: Optional[int]
            force_total=None,  # type: Optional[int]
            log_prefix='',  # type: str
            batch_size=50,  # type: int
    ):  # type: (...) -> list

        result, err = call_list_method(self, method, fields=fields,
                                limit=limit,
                                allowable_error=allowable_error,
                                timeout=timeout,
                                log_prefix=log_prefix,
                                batch_size=batch_size,
                                v=2)
        if err:  # Во второй версии всегда кидаем ошибки
            raise CallListException(err)
        return result




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
        from ..functions.call_list_fast import call_list_fast
        return call_list_fast(self, method, params, descending=descending,
                              limit=limit, batch_size=batch_size,
                              timeout=timeout, log_prefix=log_prefix)



    @classmethod
    def refresh_all(cls, timeout=DEFAULT_TIMEOUT):
        """Обновить все токены, неудачи игнорятся.

        :param timeout: таймаут обновления каждого конкретного токена.
        """
        # to_refresh = BitrixUserToken.objects.filter(is_active=True)
        to_refresh = BitrixUserToken.objects.filter(application__is_webhook=False)
        active_from = to_refresh.filter(is_active=True).count()
        active_to = 0
        for instance in to_refresh:
            if instance.refresh(timeout=timeout):
                active_to += 1
        return "%s -> %s" % (active_from, active_to)

    def hello_world(self, *args, **kwargs):  # ?
        return u'hello_world'

    def __unicode__(self):
        try:
            return u"#{}@{} of {!r}".format(self.id, "domain", self.user if self.id else 'dynamic_token')
        except:
            return u"#{}@{} of user.{!r}".format(self.id, "domain", self.user_id if self.id else 'dynamic_token')

    __str__ = __unicode__

    call_api_method_v2 = call_api_method