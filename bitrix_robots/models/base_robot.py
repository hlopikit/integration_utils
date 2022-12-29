from typing import Callable

from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.conf import settings

from integration_utils.bitrix24.bitrix_user_auth.main_auth import main_auth
from integration_utils.bitrix24.functions.api_call import api_call
from integration_utils.bitrix24.models import BitrixUserToken, BitrixUser
from integration_utils.bitrix_robots.errors import VerificationError
from integration_utils.bitrix_robots.base import BaseBitrixRobot


class BaseRobot(BaseBitrixRobot):
    APP_DOMAIN = settings.APP_SETTINGS.app_domain  # type: str

    token = models.ForeignKey('bitrix24.BitrixUserToken', null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        abstract = True

    @classmethod
    def get_hook_auth_decorator(cls) -> Callable:
        return main_auth(on_cookies=True)

    @classmethod
    def from_hook_request(cls, request) -> 'BaseBitrixRobot':
        return cls.objects.create(
            token=request.bitrix_user_token,
            params=request.its_params,
            is_hook_request=True,
        )

    @cached_property
    def dynamic_token(self) -> BitrixUserToken:
        """не конструирует динамический BitrixUserToken.
        fixme: deprecated
        """
        return self.token

    @property
    def bx_user(self) -> BitrixUser:
        """fixme: deprecated
        """
        return self.user

    def verify_event(self):
        """Проверка подлинности присланного события.
        Несколько усложняется тем, что у нас несколько приложений Базы Знаний.

        :raises: VerificationError
        """

        auth = self.get_auth_dict()

        application_token = settings.APP_SETTINGS.application_token
        if not (application_token and application_token == auth['application_token']):
            resp = api_call(settings.APP_SETTINGS.portal_domain, 'app.info', auth_token=auth['access_token'], timeout=1)
            try:
                assert resp.ok and resp.json()['result']['CODE'] == settings.APP_SETTINGS.application_bitrix_client_id
            except (ValueError, AssertionError):
                raise VerificationError('invalid auth: {}'.format(auth))

        try:
            self.event_token = self.params['event_token']
        except KeyError:
            raise VerificationError('no event token (POST[event_token])')

        user, _ = BitrixUser.objects.get_or_create(bitrix_id=self.params["auth[user_id]"])
        self.token, _ = BitrixUserToken.objects.get_or_create(
            user=user,
            defaults=dict(
                auth_token=auth['access_token'],
                refresh_token=self.params.get('auth[refresh_token]', ''),
                auth_token_date=timezone.now(),
                is_active=True,
            ),
        )

    def process(self) -> dict:
        """
        Обработать запрос
        self.props - параметры
        self.token - токен
        """
        raise NotImplementedError
