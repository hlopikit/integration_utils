from functools import wraps
from typing import Optional, Callable, TYPE_CHECKING, Union, Any

from django.contrib import admin
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpRequest, QueryDict, JsonResponse
from django.conf import settings
from django.core.exceptions import ValidationError

from integration_utils.its_utils.app_get_params import get_params_from_sources
from integration_utils.bitrix_robots.errors import VerificationError, DelayProcess
from integration_utils.bitrix_robots.helpers import get_php_style_list
from settings import ilogger

import django

if django.VERSION[0] >= 3:
    from django.db.models import JSONField
else:
    from django.contrib.postgres.fields import JSONField

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

    # True активирует валидацию пропсов, которые кинул битрикс с помощью validate_props
    VALIDATE_PROPS = False

    token = models.ForeignKey('BitrixUserToken', on_delete=models.PROTECT)
    event_token = models.CharField(max_length=255, null=True, blank=True)
    params = JSONField()

    dt_add = models.DateTimeField(default=timezone.now)
    started = models.DateTimeField(null=True, blank=True, db_index=True)
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
        """
        Привести параметры к нужным типам
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
                # числа с большой разрядностью ведут сбя странно при сохранении в jsonfield
                self.params[prop] = str(self.params[prop])

    @classmethod
    def handler_url(cls, view_name):
        """
        Получить URL обработчика через reverse+название view
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
        """
        Зарегистрирован ли робот на портале
        """
        robot_codes = admin_token.call_list_method_v2('bizproc.robot.list')
        return any(code == cls.CODE for code in robot_codes)

    @classmethod
    def install(cls, view_name: str, admin_token: 'BitrixUserToken', token_user: Optional['BitrixUser'] = None):
        """
        Встроить робота на портал
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
        """
        Удалить робота с портала
        """
        return admin_token.call_api_method(
            'bizproc.robot.delete',
            params=dict(CODE=cls.CODE),
        )['result']

    @classmethod
    def update(cls, view_name: str, admin_token: 'BitrixUserToken', token_user: Optional['BitrixUser'] = None):
        """
        Обновить параметры робота на портале
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
    def install_or_update(cls, view_name: str, admin_token: 'BitrixUserToken', token_user: 'BitrixUser' = None):
        """
        Встроить или обновить параметры робота на портале
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
                        'robot_processing_error_{}'.format(cls_name),
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
        """
        Проверка подлинности присланного события.
        Несколько усложняется тем, что у нас несколько приложений Базы Знаний.

        :raises: VerificationError
        """
        raise NotImplementedError

    @property
    def user(self) -> 'BitrixUser':
        return self.token.user

    @staticmethod
    def _check_required(value: Any):
        """
        Проверяет, что обязательное поле не пустое.
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValidationError('Поле обязательно для заполнения')

    @staticmethod
    def safe_int(value: Optional[Union[int, str]], required: bool = False) -> Optional[int]:
        """
        Преобразует значение в int, если это возможно.
        Если значение пустое или None, возвращает None.
        При неудаче выбрасывает ValidationError.
        """
        if required:
            BaseBitrixRobot._check_required(value)

        if value is None:
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return int(stripped)
            except ValueError:
                raise ValidationError(f'Значение "{stripped}" не может быть преобразовано в число')

        # Если значение ни строка, ни число – выбрасываем ошибку валидации
        raise ValidationError('Значение должно быть строкой или числом')

    @staticmethod
    def safe_bool(value: Optional[Union[bool, str]], required: bool = False) -> Optional[bool]:
        """
        Производит валидацию и нормализацию логических пропсов.
        'Y' = True
        'N', '', и None = False, если поле не является обязательным.
        Если поле обязательно (required==True) и значение пустое, выбрасывает ошибку.
        """
        if required:
            BaseBitrixRobot._check_required(value)

        if value is None:
            return False

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return False
            if stripped == 'Y':
                return True
            if stripped == 'N':
                return False

        raise ValidationError(f"Значение '{value}' не может быть преобразовано в bool")

    @staticmethod
    def safe_string(value: Optional[str], required: bool = False) -> Optional[str]:
        """
        Проверяет и возвращает строку.
        """
        if required:
            BaseBitrixRobot._check_required(value)

        if value is None:
            return None

        if isinstance(value, str):
            return value

        raise ValidationError('Значение должно быть строкой')

    @staticmethod
    def safe_text(value: Optional[str], required: bool = False) -> Optional[str]:
        """
        Проверяет и возвращает текст.
        """
        if required:
            BaseBitrixRobot._check_required(value)

        if value is None:
            return None

        if isinstance(value, str):
            return value

        raise ValidationError('Значение должно быть текстом')

    def validate_props(self) -> dict:
        """
        Проверяет типы значений свойств, которые прислал Битрикс.
        Сейчас проверяет одиночные int, bool, string и text.
        """
        errors = []

        for prop_name, prop_value in self.props.items():
            try:
                prop_config = self.PROPERTIES.get(prop_name, {})
                prop_type = prop_config.get('Type')
                multiple = prop_config.get('Multiple')
                required = prop_config.get('Required', 'N') == 'Y'

                if prop_type == 'int' and multiple != 'Y':
                    self.props[prop_name] = self.safe_int(prop_value, required=required)

                elif prop_type == 'bool' and multiple != 'Y':
                    self.props[prop_name] = self.safe_bool(prop_value, required=required)

                elif prop_type == 'string' and multiple != 'Y':
                    self.props[prop_name] = self.safe_string(prop_value, required=required)

                elif prop_type == 'text' and multiple != 'Y':
                    self.props[prop_name] = self.safe_text(prop_value, required=required)

            except ValidationError as exc:
                errors.append(f'Ошибка в поле "{prop_name}": {exc.message}.')

        if errors:
            # Если есть хотя бы одна ошибка, выбрасываем их все одним исключением
            raise ValidationError(' '.join(errors))

        return self.props

    @cached_property
    def props(self) -> dict:
        """
        Разбирает присланные данные на основании PROPERTIES
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
            if self.VALIDATE_PROPS:
                self.validate_props()

            self.result = self.process()
            self.is_success = True

        except DelayProcess:
            # вернуть запрос в очередь
            self.started = None
            self.save(update_fields=['started'])
            return

        except ValidationError as exc:
            self.result = self.get_error_result(exc)
            self.is_success = False
            ilogger.warning(f'robot_validation_error_{type(self).__name__}', f'request id {self.id}: {exc.message}')

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

    @staticmethod
    def get_error_result(exc: Exception) -> dict:
        if hasattr(exc, 'message'):
            return dict(error=exc.message)
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


    @classmethod
    def process_robot_requests(cls):
        from integration_utils.bitrix_robots.cron import process_robot_requests
        return process_robot_requests(cls)
