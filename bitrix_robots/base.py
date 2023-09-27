from functools import wraps
from typing import Optional, Callable, TYPE_CHECKING

from django.contrib import admin
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpRequest, QueryDict, JsonResponse
from django.conf import settings

from integration_utils.its_utils.app_get_params import get_params_from_sources
from integration_utils.bitrix_robots.errors import VerificationError, DelayProcess
from integration_utils.bitrix_robots.helpers import get_php_style_list
from its_utils.functions.compatibility import get_json_field
from settings import ilogger

import django

JSONField = get_json_field()

if TYPE_CHECKING:
    from integration_utils.bitrix24.models import BitrixUserToken, BitrixUser


class BaseBitrixRobot(models.Model):
    CODE = NotImplemented  # type: str
    NAME = NotImplemented  # type: str

    APP_DOMAIN = getattr(settings, 'DOMAIN', '')  # type: str

    PROPERTIES = {}
    RETURN_PROPERTIES = {}

    # USE_SUBSCRIPTION = None: пользователь выбирает ждать ли ответа (работает ненадежно)
    # USE_SUBSCRIPTION = True: всегда ждать ответа робота
    # USE_SUBSCRIPTION = False: никогда не ждать ответа робота
    USE_SUBSCRIPTION = None
    USE_PLACEMENT = False

    # Обрабатывать сразу после получения запроса
    # Если False, обрабатывать в integration_utils.bitrix_robots.cron.process_robot_requests
    PROCESS_ON_REQUEST = True

    token = models.ForeignKey('BitrixUserToken', on_delete=models.PROTECT)
    event_token = models.CharField(max_length=255, null=True, blank=True)
    params = JSONField()

    dt_add = models.DateTimeField(auto_now=True, editable=True)
    started = models.DateTimeField(null=True, blank=True)
    finished = models.DateTimeField(null=True, blank=True)
    is_success = models.BooleanField(default=False)
    result = JSONField(null=True, blank=True)
    is_hook_request = models.BooleanField(default=False)
    send_result_response = models.TextField(null=True, blank=True)

    class Meta:
        abstract = True

    class Admin(admin.ModelAdmin):
        list_display = 'id', 'token', 'dt_add', 'started', 'finished', 'is_success'
        list_display_links = list_display
        raw_id_fields = 'token',

    def __str__(self):
        return '[{}] {} ({})'.format(self.id, self.token, self.dt_add)

    def save(self, *args, **kwargs):
        self.fix_json_params()
        super().save(*args, **kwargs)

    def fix_json_params(self):
        """привести параметры к нужным типам
        """

        if self.is_hook_request:
            return

        for prop_name, desc in self.PROPERTIES.items():
            prop = None
            for prop_var in ['properties[{}]'.format(prop_name), 'properties[{}][0]'.format(prop_name)]:
                if prop_var in self.params:
                    prop = prop_var

            if not prop:
                return

            if desc.get('Multiple') != 'Y' and desc.get('Type') == 'string':
                # числа с большой разрядностью ведут сбя странно при сохранениие в jsonfield
                self.params[prop] = str(self.params[prop])

    @classmethod
    def handler_url(cls, view_name):
        """Получить URL обработчика через reverse+название view
        """
        return 'https://{domain}{path}'.format(
            domain=cls.APP_DOMAIN,
            path=reverse(view_name),
        )

    @classmethod
    def _robot_add_params(cls, view_name: str, auth_user_id: int) -> dict:
        def bx_bool(value):
            return 'Y' if value else 'N'

        params = dict(
            AUTH_USER_ID=auth_user_id,
            CODE=cls.CODE,
            HANDLER=cls.handler_url(view_name),
            NAME=cls.NAME,
            USE_PLACEMENT=bx_bool(cls.USE_PLACEMENT),
        )

        # Если передавать пустые объекты возникает ошибка:
        # {'error_description': 'Wrong property key (0)!',
        #  'error': 'ERROR_ACTIVITY_VALIDATION_FAILURE'}
        if cls.PROPERTIES:
            params['PROPERTIES'] = cls.PROPERTIES
        if cls.RETURN_PROPERTIES:
            params['RETURN_PROPERTIES'] = cls.RETURN_PROPERTIES
        if cls.USE_SUBSCRIPTION is not None:
            params['USE_SUBSCRIPTION'] = bx_bool(cls.USE_SUBSCRIPTION)

        return params

    @classmethod
    def _robot_update_params(cls, view_name: str, auth_user_id: int) -> dict:
        add_params = cls._robot_add_params(view_name, auth_user_id)
        code = add_params.pop('CODE')
        return dict(CODE=code, FIELDS=add_params)

    @classmethod
    def is_installed(cls, admin_token: 'BitrixUserToken') -> bool:
        """Зарегистрирован ли робот на портале
        """
        robot_codes = admin_token.call_list_method_v2('bizproc.robot.list')
        return any(code == cls.CODE for code in robot_codes)

    @classmethod
    def install(cls, view_name: str, admin_token: 'BitrixUserToken',
                token_user: Optional['BitrixUser'] = None):
        """Встроить робота на портал
        """
        if token_user:
            assert token_user.id == admin_token.user_id
        else:
            token_user = admin_token.user

        return admin_token.call_api_method(
            'bizproc.robot.add',
            params=cls._robot_add_params(view_name, token_user.bitrix_id),
        )['result']

    @classmethod
    def uninstall(cls, admin_token: 'BitrixUserToken'):
        """Удалить робота с портала
        """

        return admin_token.call_api_method(
            'bizproc.robot.delete',
            params=dict(CODE=cls.CODE),
        )['result']

    @classmethod
    def update(cls, view_name: str, admin_token: 'BitrixUserToken',
               token_user: Optional['BitrixUser'] = None):
        """Обновить параметры робота на портале
        """
        if token_user:
            assert token_user.id == admin_token.user_id
        else:
            token_user = admin_token.user

        return admin_token.call_api_method(
            'bizproc.robot.update',
            params=cls._robot_update_params(view_name, token_user.bitrix_id),
        )['result']

    @classmethod
    def install_or_update(cls, view_name: str, admin_token: 'BitrixUserToken',
                          token_user: 'BitrixUser' = None):
        """Встроить или обновить параметры робота на портале
        """
        if cls.is_installed(admin_token):
            method = cls.update
        else:
            method = cls.install

        return method(view_name=view_name, admin_token=admin_token, token_user=token_user)

    @classmethod
    def as_view(cls):
        @get_params_from_sources
        @csrf_exempt
        @wraps(cls.start_process)
        def view(request: HttpRequest):
            cls_name = cls.__name__

            ilogger.debug(
                'new_robot_request_{}'.format(cls_name),
                '{request.POST!r}'.format(request=request),
            )

            try:
                robot = cls(params=request.its_params)

                try:
                    robot.verify_event()
                except VerificationError as e:
                    ilogger.error(
                        'robot_verification_error_{}'.format(cls_name),
                        '{e!r}\nPOST: {request.POST!r}'.format(e=e, request=request),
                    )
                    return e.http_response()

                robot.save()

            except Exception as e:
                ilogger.error(
                    'robot_view_unexpected_error_{}'.format(cls_name),
                    '{e!r}\nPOST: {request.POST!r}'.format(e=e, request=request),
                )
                return HttpResponse('error')

            if cls.PROCESS_ON_REQUEST:
                try:
                    robot.start_process()
                except Exception as e:
                    ilogger.error(
                        'robot_processings_error_{}'.format(cls_name),
                        '{e!r}\nPOST: {request.POST!r}'.format(e=e, request=request),
                    )
                    return HttpResponse('error')

            return HttpResponse('ok')

        return view

    @classmethod
    def get_hook_auth_decorator(cls) -> Callable:
        raise NotImplementedError

    @classmethod
    def from_hook_request(cls, request) -> 'BaseBitrixRobot':
        raise NotImplementedError

    @classmethod
    def as_hook(cls):
        @csrf_exempt
        @get_params_from_sources
        @cls.get_hook_auth_decorator()
        @wraps(cls.process)
        def view(request):
            robot = cls.from_hook_request(request)

            if not cls.PROCESS_ON_REQUEST:
                return JsonResponse(dict(request_id=robot.id))

            robot.start_process()
            return JsonResponse(robot.result)

        return view

    def get_auth_dict(self) -> dict:
        auth = {}
        for key in ['member_id', 'access_token', 'application_token', 'user_id']:
            auth_key = 'auth[{}]'.format(key)
            try:
                auth[key] = self.params[auth_key]
            except KeyError:
                raise VerificationError('no {}'.format(key))

        return auth

    def verify_event(self):
        """Проверка подлинности присланного события.
        Несколько усложняется тем, что у нас несколько приложений Базы Знаний.

        :raises: VerificationError
        """
        raise NotImplementedError

    @property
    def user(self) -> 'BitrixUser':
        return self.token.user

    @cached_property
    def props(self) -> dict:
        """Разбирает присланные данные на основании PROPERTIES
        """

        if self.is_hook_request:
            return self.params.get('properties', {})

        res = {}
        query_dict_params = self.get_query_dict_params()
        for prop, desc in self.PROPERTIES.items():
            full_prop = 'properties[%s]' % prop
            # иногда параметры приходят в виде 'properties[prop_name][0]', даже если поле не множественное
            full_prop_0 = 'properties[%s][0]' % prop
            default = desc.get('Default')

            if desc.get('Multiple') == 'Y':
                res[prop] = get_php_style_list(query_dict_params, full_prop, [])
            else:
                res[prop] = self.params.get(full_prop, self.params.get(full_prop_0, default))

        return res

    def get_query_dict_params(self):
        query_dict = QueryDict('', mutable=True)
        query_dict.update(self.params)
        return query_dict

    def use_subscription(self):
        return self.params.get('use_subscription') == 'Y'

    def start_process(self):
        self.started = timezone.now()
        self.save(update_fields=['started'])

        try:
            self.result = self.process()
            self.is_success = True

        except DelayProcess:
            # вернуть запрос  в очередь
            self.started = None
            self.save(update_fields=['started'])
            return

        except Exception as exc:
            self.result = self.get_error_result(exc)
            self.is_success = False

            ilogger.error(
                'process_robot_request_error_{}'.format(type(self).__name__),
                'request {}: {}'.format(self.id, exc),
            )

        self.finished = timezone.now()
        self.save(update_fields=['finished', 'result', 'is_success'])
        self.send_result()
        return self.result

    def get_error_result(self, exc: Exception) -> dict:
        return dict(error=str(exc))

    def get_return_values(self) -> dict:
        return_values = {}

        for key, value in self.result.items():
            if isinstance(value, bool):
                value = 'Y' if value else 'N'
            return_values[key] = value

        return return_values

    def send_result(self):
        if self.is_hook_request or not self.use_subscription():
            # бп не ждёт результат
            return

        try:
            self.send_result_response = str(self.token.call_api_method('bizproc.event.send', dict(
                event_token=self.event_token,
                return_values=self.get_return_values(),
            )))

        except Exception as exc:
            ilogger.warning('robot_send_result_{}_{}'.format(
                '404' if getattr(exc, 'error', None) == 404 else 'error',
                type(self).__name__), str(exc),
            )
            self.send_result_response = 'Error! {}'.format(exc)

        self.save(update_fields=['send_result_response'])

    def process(self) -> dict:
        """
        Обработать запрос
        self.props - параметры
        self.token - токен
        """
        raise NotImplementedError
