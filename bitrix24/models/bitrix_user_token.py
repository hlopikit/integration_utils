# -*- coding: UTF-8 -*-

import hashlib
import typing

import requests
from django.conf import settings
from django.db import models

from django.utils import timezone

from integration_utils.bitrix24.functions.api_call import BitrixTimeout
from integration_utils.bitrix24.exceptions import BitrixApiError, ExpiredToken, BaseConnectionError, BaseTimeout, BitrixApiException
from integration_utils.bitrix24.bitrix_token import BaseBitrixToken
from integration_utils.iu_retry_manager.retry_decorator import retry_decorator
from settings import ilogger

if typing.TYPE_CHECKING:
    from integration_utils.bitrix24.models import BitrixUser


def refresh_all():
    return BitrixUserToken.refresh_all()


class BitrixUserToken(models.Model, BaseBitrixToken):
    DEFAULT_TIMEOUT = getattr(settings, 'BITRIX_RESTAPI_DEFAULT_TIMEOUT', 10)

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
    # можно переопределить домен для рест методов для кластеров
    rest_domain = getattr(settings, 'REST_DOMAIN', None)
    domain = rest_domain or settings.APP_SETTINGS.portal_domain
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

    @classmethod
    def get_random_token(cls, is_admin=True, pk_desc=False, bitrix_unavailable_attempts = 2):
        """
        Получить один любой активный токен

        :param is_admin: токен должен иметь права администратора (True - да, False - админский при наличии, иначе простого юзера)
        :param pk_desc: брать сначала последние токены
        :param bitrix_unavailable_attempts: число запросов в Битрикс, если он недоступен
        :raise BitrixUserTokenDoesNotExist: не найден подходящий токен
        :raise BaseConnectionError/BaseTimeout: не удалось достучаться до Битрикс после всех попыток
        """
        log_tag = 'integration_utils.BitrixUserToken.get_random_token'

        @retry_decorator(bitrix_unavailable_attempts, (BaseConnectionError, BaseTimeout))
        def update_is_admin_with_retries(bx_user: 'BitrixUser', bx_token):
            bx_user.update_is_admin(bx_token, save_is_admin=True, save_is_active=False, fail_silently=False)

        tokens = cls.objects.filter(
            user__user_is_active=True,
            is_active=True,
        ).exclude(
            user__extranet=True,  # Не хотим внешних пользователей, так как ограничены в правах
        )

        if is_admin:
            tokens = tokens.filter(user__is_admin=True)
        else:
            tokens = tokens.order_by('-user__is_admin')

        tokens = tokens.order_by(f'{"-" if pk_desc else ""}pk')

        result_token = None
        likely_inactive_user_dict = {}

        for token in tokens:
            user = token.user

            try:
                update_is_admin_with_retries(user, token)
            except BitrixApiError as e:
                log_function = ilogger.warning if e.is_not_logic_error else ilogger.error
                log_function('update_is_admin_bitrix_api_exception', f"({e}): user={user}, token={token}", tag=log_tag, exc_info=True)
                continue

            user_is_active = user.user_is_active
            user_is_admin = user.is_admin

            # Берём следующий токен, если:
            # - пользователь не активный
            # - пользователь не админ, когда нужен админ
            if not user_is_active:
                likely_inactive_user_dict[str(user.bitrix_id)] = user
            elif not is_admin or user_is_admin:
                result_token = token
                break

        if result_token is None:
            raise BitrixUserToken.DoesNotExist()
        else:
            # Смотрим, были ли найдены потенциально неактивные пользователи
            if likely_inactive_user_dict:
                likely_inactive_user_bitrix_ids = list(likely_inactive_user_dict.keys())

                try:
                    # Делаем запрос в Битрикс для проверки потенциально неактивных пользователей
                    bitrix_users = result_token.call_api_method('user.get', {
                        'FILTER': {
                            'ID': likely_inactive_user_bitrix_ids,
                        },
                    })['result']
                except BitrixApiException as e:
                    log_function = ilogger.warning if e.is_not_logic_error else ilogger.error
                    log_function(
                        'user_get_bitrix_api_exception',
                        f"({e}): result_token={result_token}, likely_inactive_user_bitrix_ids={likely_inactive_user_bitrix_ids}",
                        tag=log_tag, exc_info=True,
                    )
                except Exception as e:
                    ilogger.error(
                        'user_get_exception',
                        f"({e}): result_token={result_token}, likely_inactive_user_bitrix_ids={likely_inactive_user_bitrix_ids}",
                        tag=log_tag,
                    )
                else:
                    bulk_update_users = []
                    for bitrix_user in bitrix_users:
                        bitrix_user_id = str(bitrix_user['ID'])
                        bitrix_user_active = bitrix_user.get('ACTIVE', None)
                        if bitrix_user_active is not None and not bitrix_user_active:
                            # Добавляем реально неактивных пользователей в массив для обновления
                            bulk_update_user = likely_inactive_user_dict.get(bitrix_user_id)
                            if bulk_update_user:
                                bulk_update_users.append(bulk_update_user)

                    if bulk_update_users:
                        from bitrix_utils.bitrix_auth.models import BitrixUser
                        BitrixUser.objects.bulk_update(bulk_update_users, ['user_is_active'])

        return result_token

    def refresh(self, timeout=60):
        """
        Если успешно обновился токен, то возвращаем True
        Если что-то пошло не так то False

        :param timeout: таймаут запроса
        """
        if not self.pk:
            # Динамический токен
            #raise BitrixApiError(401, dict(error='expired_token'))
            raise BitrixApiError(has_resp='deprecated', json_response=dict(error='expired_token'), status_code=401, message='expired_token')

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
            if response.status_code >= 403 and "portal404" in response.text:
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
            return super().call_api_method(api_method=api_method, params=params, timeout=timeout)
        except ExpiredToken:
            if self.refresh(timeout=timeout):
                # Если обновление токена прошло успешно, повторить запрос
                return self.call_api_method(api_method, params, timeout=timeout)
            raise

    def deactivate_token(self, refresh_error):
        if self.pk:
            self.is_active = False
            self.refresh_error = refresh_error
            self.save(force_update=True)

    def batch_api_call(self, methods, timeout=DEFAULT_TIMEOUT, chunk_size=50, halt=0, log_prefix=''):
        """:rtype: bitrix_utils.bitrix_auth.functions.batch_api_call3.BatchResultDict
        """
        from integration_utils.bitrix24.exceptions import BatchApiCallError
        try:
            return super().batch_api_call(methods=methods,
                                          timeout=timeout,
                                          chunk_size=chunk_size,
                                          halt=halt,
                                          log_prefix=log_prefix)
        except BatchApiCallError as e:
            # fixme: нет такого метода
            # self.check_deactivate_errors(e.reason)
            raise e

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

    @classmethod
    def get_admin_token(cls):
        return cls.get_random_token(is_admin=True)

    def __unicode__(self):
        try:
            return u"#{}@{} of {!r}".format(self.id, "domain", self.user if self.id else 'dynamic_token')
        except:
            return u"#{}@{} of user.{!r}".format(self.id, "domain", self.user_id if self.id else 'dynamic_token')

    __str__ = __unicode__

    call_api_method_v2 = call_api_method
