# -*- coding: UTF-8 -*-

import hashlib
import typing
from datetime import timedelta

import requests
from django.conf import settings
from django.db import models

from django.utils import timezone

from integration_utils.bitrix24.exceptions import BitrixApiError, ExpiredToken, BaseConnectionError, BaseTimeout, BitrixApiException, \
    BitrixOauthRefreshConnectionError, BitrixOauthRefreshTimeout, BitrixOauthRefreshRequestException, BitrixConnectionError, BitrixTimeout
from integration_utils.bitrix24.bitrix_token import BaseBitrixToken
from integration_utils.iu_retry_manager.retry_decorator import retry_decorator
from settings import ilogger

if typing.TYPE_CHECKING:
    from integration_utils.bitrix24.models import BitrixUser


def refresh_all():
    return BitrixUserToken.refresh_all()


class BitrixUserToken(models.Model, BaseBitrixToken):
    DEFAULT_TIMEOUT = getattr(settings, 'BITRIX_RESTAPI_DEFAULT_TIMEOUT', 10)
    TOKEN_REFRESH_RESERVE_SECONDS = 30

    NO_ERROR = 0

    WRONG_CLIENT = 1
    EXPIRED_TOKEN = 2
    INVALID_GRANT = 3
    NOT_INSTALLED = 4
    PAYMENT_REQUIRED = 5
    DOMAIN_ERROR = 6
    OAUTH_GTE_500 = 8
    UNKNOWN_ERROR = 9
    PORTAL_DELETED = 10
    NO_CLIENT_CREDENTIALS = 11
    APPLICATION_NOT_INSTALLED = 12
    ERROR_403_or_404 = 13
    NO_AUTH_FOUND = 14
    AUTHORIZATION_ERROR = 15
    ACCESS_DENIED = 16
    APPLICATION_NOT_FOUND = 17
    USER_ACCESS_ERROR = 19
    FREE_PLAN_ERROR = 20
    UNABLE_TO_AUTHORIZE_USER = 21
    USER_CANT_BE_AUTHORIZED_IN_CONTEXT = 22

    # Для обратной совместимости
    ERROR_CORE = NO_CLIENT_CREDENTIALS
    ERROR_OAUTH = APPLICATION_NOT_INSTALLED

    REFRESH_ERRORS = (
        (NO_ERROR, 'Нет ошибки'),
        (WRONG_CLIENT, 'Неверный client_id/secret приложения (WRONG_CLIENT)'),
        (EXPIRED_TOKEN, 'Просроченный токен при обновлении (EXPIRED_TOKEN)'),
        (INVALID_GRANT, 'Неверный токен при обновлении (INVALID_GRANT)'),
        (NOT_INSTALLED, 'Приложение не установлено (NOT_INSTALLED)'),
        (PAYMENT_REQUIRED, 'Не оплачена подписка (PAYMENT_REQUIRED)'),
        (DOMAIN_ERROR, 'Домен отключён или не существует (DOMAIN_ERROR)'),
        (OAUTH_GTE_500, 'Ошибка сервера авторизации (OAUTH_GTE_500)'),
        (UNKNOWN_ERROR, 'Неизвестная ошибка (UNKNOWN_ERROR)'),
        (PORTAL_DELETED, 'Публичная часть сайта закрыта (PORTAL_DELETED)'),
        (NO_CLIENT_CREDENTIALS, 'Портал без service_client_id/secret (NO_CLIENT_CREDENTIALS)'),
        (APPLICATION_NOT_INSTALLED, 'Приложение не установлено (APPLICATION_NOT_INSTALLED)'),
        (ERROR_403_or_404, 'Доступ запрещён (ERROR_403_or_404)'),
        (NO_AUTH_FOUND, 'Неверная авторизация (NO_AUTH_FOUND)'),
        (AUTHORIZATION_ERROR, 'Ошибка авторизации (AUTHORIZATION_ERROR)'),
        (ACCESS_DENIED, 'Нет доступа (ACCESS_DENIED)'),
        (APPLICATION_NOT_FOUND, 'Не найдено приложение (APPLICATION_NOT_FOUND)'),
        (USER_ACCESS_ERROR, 'Пользователь не имеет доступа к приложению (USER_ACCESS_ERROR)'),
        (FREE_PLAN_ERROR, 'Бесплатный тариф (FREE_PLAN_ERROR)'),
        (UNABLE_TO_AUTHORIZE_USER, 'Пользователь уволен или заблокирован (UNABLE_TO_AUTHORIZE_USER)'),
        (USER_CANT_BE_AUTHORIZED_IN_CONTEXT, 'Пользователь удалён или не подтверждён (USER_CANT_BE_AUTHORIZED_IN_CONTEXT)'),
    )

    AUTH_COOKIE_MAX_AGE = None   # as long as the client’s browser session
    # можно переопределить домен для REST методов для кластеров
    rest_domain = getattr(settings, 'REST_DOMAIN', None)
    domain = rest_domain or settings.APP_SETTINGS.portal_domain
    web_hook_auth = None
    application = None

    user = models.OneToOneField('BitrixUser', related_name='bitrix_user_token', on_delete=models.CASCADE)

    auth_token = models.CharField(max_length=70)
    refresh_token = models.CharField(max_length=70, default='', blank=True)
    auth_token_date = models.DateTimeField()
    expires_at = models.DateTimeField(default=None, null=True, blank=True)
    app_sid = models.CharField(max_length=70, blank=True)

    is_active = models.BooleanField(default=True)
    refresh_error = models.PositiveSmallIntegerField(default=0, choices=REFRESH_ERRORS)

    def __init__(self, *args, **kwargs):
        # 1) Могут в БД лежать уже готовые токены и тогда просто их используем
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
        # Используется в декораторе bitrix_user_required для пользовательских АПИ запросов из приложений
        pk = cls.check_token(token)
        if pk:
            return cls.objects.get(pk=pk)

    @classmethod
    def check_token(cls, token):
        # TODO: Проверить актуальность
        pk, token = token.split('::')
        # except (AttributeError, ValueError):
        #     return
        if token == cls.get_auth_token(pk):
            return pk

    @classmethod
    def get_random_token(cls, is_admin=True, pk_desc=False, bitrix_unavailable_attempts = 2):
        """
        Получить один любой активный токен.

        :param is_admin: токен должен иметь права администратора (True - да, False - админский при наличии, иначе простого юзера)
        :param pk_desc: брать сначала последние токены
        :param bitrix_unavailable_attempts: число запросов в Битрикс, если он недоступен
        :raise BitrixUserTokenDoesNotExist: не найден подходящий токен
        :raise BitrixApiException: различные нерешаемые ошибки Битрикс
        """
        log_tag = 'integration_utils.BitrixUserToken.get_random_token'

        @retry_decorator(bitrix_unavailable_attempts, (BaseConnectionError, BaseTimeout))
        def update_is_admin_with_retries(bx_user: 'BitrixUser', bx_token: 'BitrixUserToken'):
            bx_user.update_is_admin(bx_token, save_is_admin=True, save_is_active=False, fail_silently=False)

        tokens = cls.objects.filter(
            user__user_is_active=True,
            is_active=True,
        ).exclude(
            user__extranet=True,  # Не хотим внешних пользователей, так как ограничены в правах
        )

        if is_admin:
            tokens = tokens.filter(user__is_admin=True).order_by(f'{"-" if pk_desc else ""}pk')
        else:
            tokens = tokens.order_by('-user__is_admin', f'{"-" if pk_desc else ""}pk')

        result_token = None
        likely_inactive_user_dict = {}

        for token in tokens:
            user = token.user

            try:
                update_is_admin_with_retries(user, token)
            except BitrixApiError as e:
                if e.is_user_access_error or e.is_token_expired:
                    ilogger.warning('update_is_admin_bx_api_err', f"({e}): token={token}", exc_info=True, tag=log_tag)
                    continue
                raise e

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
                        from integration_utils.bitrix24.models.bitrix_user import BitrixUser
                        BitrixUser.objects.bulk_update(bulk_update_users, ['user_is_active'])

        return result_token

    def refresh(self, timeout=60, check_api_call=True):
        """
        Если успешно обновился токен, то возвращаем True.
        Если что-то пошло не так, то False.

        :param timeout: таймаут запроса
        :param check_api_call: проверить работу API-запросов после обновления
        :raise BitrixApiError: ошибка обновления.
        :raise BitrixOauthRefreshTimeout: таймаут при обновлении токена.
        :raise BitrixOauthRefreshConnectionError: ошибка соединения при обновлении токена.
        :raise BitrixOauthRefreshRequestException: прочая ошибка при обновлении токена.
        """
        log_tag = 'integration_utils.bitrix24.BitrixUserToken.refresh'

        if not self.pk:
            # Динамический токен
            # raise BitrixApiError(401, dict(error='expired_token'))
            raise BitrixApiError(has_resp='deprecated', json_response=dict(error='expired_token'), status_code=401, message='expired_token')

        params = {
            'grant_type': 'refresh_token',
            'client_id': settings.APP_SETTINGS.application_bitrix_client_id,
            'client_secret': settings.APP_SETTINGS.application_bitrix_client_secret,
            'refresh_token': self.refresh_token,
        }
        params = '&'.join(['%s=%s' % (k, v) for k, v in params.items()])
        url = 'https://oauth.bitrix24.tech/oauth/token/?{}'.format(params)

        try:
            response = requests.get(url, timeout=timeout)
        except requests.ConnectionError as e:
            raise BitrixOauthRefreshConnectionError(requests_connection_error=e) from e
        except requests.Timeout as e:
            raise BitrixOauthRefreshTimeout(requests_timeout=e, timeout=timeout) from e
        except requests.RequestException as e:
            raise BitrixOauthRefreshRequestException(requests_exception=e) from e

        log_message = f"self={self}, url={url}, response.text={response.text}"

        if response.status_code >= 500:
            ilogger.warning('refresh_token_error_gte500', log_message, tag=log_tag)
            self.refresh_error = self.OAUTH_GTE_500
            self.save(update_fields=['refresh_error'])
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

        error = response_json.get('error')

        if error:
            ilogger.warning(f'refresh_token_error_{error}', log_message, tag=log_tag)
            if error == 'wrong_client':
                self.refresh_error = self.WRONG_CLIENT
            elif error == 'expired_token':
                self.refresh_error = self.EXPIRED_TOKEN
            elif error == 'invalid_grant':
                self.refresh_error = self.INVALID_GRANT
            elif error == 'NOT_INSTALLED':
                self.refresh_error = self.NOT_INSTALLED
            elif error == 'PAYMENT_REQUIRED':
                self.refresh_error = self.PAYMENT_REQUIRED
            else:
                self.refresh_error = self.UNKNOWN_ERROR

            self.is_active = False
            self.save()
            return False
        else:
            self.refresh_error = self.NO_ERROR

        self.auth_token = response_json.get('access_token')
        self.refresh_token = response_json.get('refresh_token')
        self.auth_token_date = timezone.now()
        expires_in_seconds = response_json.get('expires_in')
        self.expires_at = timezone.now() + timedelta(seconds=int(expires_in_seconds)) if expires_in_seconds else None

        if check_api_call:
            try:
                # Токены, например, уволенных сотрудников успешно обновляются.
                # Но даже после обновления по токену будет кидаться ошибка из-за увольнения.
                # Делаем запрос profile, который не требует никаких разрешений.
                self.call_api_method('profile', timeout=10, refresh=False)

            except BitrixApiError as e:
                if e.is_unable_to_authorize_user:
                    self.refresh_error = self.UNABLE_TO_AUTHORIZE_USER
                elif e.is_user_cant_be_authorized_in_context:
                    self.refresh_error = self.USER_CANT_BE_AUTHORIZED_IN_CONTEXT
                elif e.is_authorization_error:
                    self.refresh_error = self.AUTHORIZATION_ERROR
                elif e.is_user_access_error:
                    self.refresh_error = self.USER_ACCESS_ERROR
                elif e.is_free_plan_error:
                    self.refresh_error = self.FREE_PLAN_ERROR

                if self.refresh_error != self.NO_ERROR:
                    self.is_active = False
                    self.save()
                    return False


            except (BitrixConnectionError, BitrixTimeout) as e:
                # Считаем, что одиночная проблема с соединением/таймаутом
                ilogger.debug('refresh_token_profile_bitrix_unavailable', f"({e}): self={self}", exc_info=True, tag=log_tag)

        ilogger.debug('refresh_token', log_message, tag=log_tag)

        if not self.is_active:
            ilogger.info('token_reactivated', f"self={self}, previous refresh_error={self.get_refresh_error_display()}", tag=log_tag)

        self.is_active = True
        self.save()

        return True

    def refresh_if_needed(self, timeout=DEFAULT_TIMEOUT):
        if self.web_hook_auth:
            return

        if not self.pk or not self.refresh_token or not self.expires_at:
            return

        refresh_before = timezone.now() + timedelta(seconds=self.TOKEN_REFRESH_RESERVE_SECONDS)
        if self.expires_at <= refresh_before:
            self.refresh(timeout=timeout)

    def call_api_method(self, api_method, params=None, timeout=DEFAULT_TIMEOUT, refresh=True):
        self.refresh_if_needed(timeout=timeout)
        try:
            return super().call_api_method(api_method=api_method, params=params, timeout=timeout)
        except ExpiredToken:
            if not refresh:
                raise ExpiredToken(status_code=401)

            if self.refresh(timeout=timeout):
                return self.call_api_method(api_method, params, timeout=timeout, refresh=False)
            raise

    def deactivate_token(self, refresh_error):
        if self.pk:
            self.is_active = False
            self.refresh_error = refresh_error
            self.save(force_update=True)

    def batch_api_call(self, methods, timeout=DEFAULT_TIMEOUT, chunk_size=50, halt=0, log_prefix='', refresh=True):
        """:rtype: bitrix_utils.bitrix_auth.functions.batch_api_call3.BatchResultDict
        """
        from integration_utils.bitrix24.exceptions import BatchApiCallError
        self.refresh_if_needed(timeout=timeout)
        try:
            return super().batch_api_call(methods=methods,
                                          timeout=timeout,
                                          chunk_size=chunk_size,
                                          halt=halt,
                                          log_prefix=log_prefix,
                                          refresh=refresh)
        except BatchApiCallError as e:
            # fixme: нет такого метода
            # self.check_deactivate_errors(e.reason)
            raise e

    @classmethod
    def refresh_all(cls, timeout=DEFAULT_TIMEOUT):
        """Обновить все токены, неудачи игнорируются.

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
        # TODO: Проверить актуальность
        return u'hello_world'

    @classmethod
    def get_admin_token(cls):
        return cls.get_random_token(is_admin=True)

    def __unicode__(self):
        # TODO: Сделать по образцу bitrix_utils
        try:
            return u"#{}@{} of {!r}".format(self.id, "domain", self.user if self.id else 'dynamic_token')
        except:
            return u"#{}@{} of user.{!r}".format(self.id, "domain", self.user_id if self.id else 'dynamic_token')

    __str__ = __unicode__

    call_api_method_v2 = call_api_method
