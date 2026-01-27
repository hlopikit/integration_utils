from typing import Callable, Optional

from django.conf import settings
from django.contrib import messages
from django.db import models
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.functional import cached_property

from integration_utils.bitrix24.bitrix_user_auth.main_auth import main_auth
from integration_utils.bitrix24.functions.api_call import api_call
from integration_utils.bitrix24.models import BitrixUserToken, BitrixUser
from integration_utils.bitrix_robots.base import BaseBitrixRobot
from integration_utils.bitrix_robots.errors import VerificationError


class BaseRobot(BaseBitrixRobot):
    APP_DOMAIN = settings.APP_SETTINGS.app_domain  # type: str

    token = models.ForeignKey('bitrix24.BitrixUserToken', null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        abstract = True

    class Admin(BaseBitrixRobot.Admin):
        change_list_template = 'bitrix_robots/admin/robot_change_list.html'

        def get_urls(self):
            """
            Что делает: добавляет admin-эндпоинты для установки и удаления робота.
            Где используется: Django-админка моделей роботов.
            """
            urls = super().get_urls()
            custom_urls = [
                path(
                    'robot-install/',
                    self.admin_site.admin_view(self.install_robot_view),
                    name=self._get_admin_url_name('install'),
                ),
                path(
                    'robot-uninstall/',
                    self.admin_site.admin_view(self.uninstall_robot_view),
                    name=self._get_admin_url_name('uninstall'),
                ),
            ]
            return custom_urls + urls

        def _get_admin_url_name(self, action: str) -> str:
            """
            Что делает: формирует уникальное имя URL для admin-эндпоинтов.
            Где используется: get_urls и reverse в changelist_view.
            """
            return f'{self.model._meta.app_label}_{self.model._meta.model_name}_{action}'

        def _get_handler_view_name(self) -> Optional[str]:
            """
            Что делает: возвращает имя handler view для установки/обновления робота.
            Где используется: install_robot_view.
            """
            return getattr(self.model, 'HANDLER_VIEW_NAME', None)

        def changelist_view(self, request, extra_context=None):
            """
            Что делает: добавляет статус установки и ссылки на действия в контекст шаблона списка.
            Где используется: отрисовка списка робота в админке.
            """
            extra_context = extra_context or {}
            token = self.model.get_admin_token()
            handler_view_name = self._get_handler_view_name()

            status_label = 'Нет активного токена администратора Битрикс24'
            status_error = None
            installed = None
            if token:
                try:
                    if not handler_view_name:
                        status_label = 'Не задан HANDLER_VIEW_NAME для установки'
                    else:
                        installed = self.model.is_installed(token)
                        status_label = 'Установлен' if installed else 'Не установлен'
                except Exception as exc:
                    status_label = 'Ошибка проверки статуса'
                    status_error = str(exc)

            extra_context.update(
                {
                    'robot_install_status': status_label,
                    'robot_install_error': status_error,
                    'robot_has_token': bool(token),
                    'robot_is_installed': installed,
                    'robot_install_url': reverse(f'admin:{self._get_admin_url_name("install")}'),
                    'robot_uninstall_url': reverse(f'admin:{self._get_admin_url_name("uninstall")}'),
                    'robot_handler_view_name': handler_view_name,
                    'robot_code': getattr(self.model, 'CODE', ''),
                    'robot_name': getattr(self.model, 'NAME', ''),
                }
            )
            return super().changelist_view(request, extra_context=extra_context)

        def install_robot_view(self, request):
            """
            Что делает: устанавливает или обновляет робота через admin-эндпоинт.
            Где используется: кнопка "Установить/обновить" в админке.
            """
            if request.method != 'POST':
                return JsonResponse({'error': 'Method is not POST'}, status=405)
            if not request.user.is_superuser:
                return JsonResponse({'error': 'Permission denied'}, status=403)

            token = self.model.get_admin_token()
            if not token:
                return JsonResponse({'error': 'Нет активного токена администратора Битрикс24'}, status=400)

            handler_view_name = self._get_handler_view_name()
            if not handler_view_name:
                return JsonResponse({'error': 'HANDLER_VIEW_NAME не задан'}, status=400)

            try:
                self.model.install_or_update(handler_view_name, token)
            except Exception as exc:
                return JsonResponse({'error': str(exc)}, status=500)

            self.message_user(request, f'Робот {self.model.CODE} установлен или обновлен.', level=messages.SUCCESS)
            return JsonResponse({'success': True})

        def uninstall_robot_view(self, request):
            """
            Что делает: удаляет робота через admin-эндпоинт.
            Где используется: кнопка "Удалить" в админке.
            """
            if request.method != 'POST':
                return JsonResponse({'error': 'Method is not POST'}, status=405)
            if not request.user.is_superuser:
                return JsonResponse({'error': 'Permission denied'}, status=403)

            token = self.model.get_admin_token()
            if not token:
                return JsonResponse({'error': 'Нет активного токена администратора Битрикс24'}, status=400)

            try:
                self.model.uninstall(token)
            except Exception as exc:
                return JsonResponse({'error': str(exc)}, status=500)

            self.message_user(request, f'Робот {self.model.CODE} удален.', level=messages.SUCCESS)
            return JsonResponse({'success': True})

    @staticmethod
    def get_admin_token() -> Optional[BitrixUserToken]:
        """
        Что делает: возвращает активный токен администратора Битрикс24.
        Где используется: проверка статуса установки и операции установки/удаления робота.
        """
        from integration_utils.bitrix24.models import BitrixUserToken
        return BitrixUserToken.get_admin_token()

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
