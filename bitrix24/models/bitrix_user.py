import typing

from django.db import models
from django.utils import timezone

from integration_utils.bitrix24.exceptions import BitrixApiError, BitrixApiException
from settings import ilogger

if typing.TYPE_CHECKING:
    from integration_utils.bitrix24.models import BitrixUserToken


class BitrixUser(models.Model):

    bitrix_id = models.IntegerField(blank=True, null=True, unique=True)  # ID

    first_name = models.CharField(max_length=255, blank=True, default='')  # NAME
    last_name = models.CharField(max_length=255, blank=True, default='')  # LAST_NAME

    # Контакты
    email = models.CharField(max_length=255)
    work_phone = models.CharField(max_length=100, blank=True, default='')  # WORK_PHONE
    personal_mobile = models.CharField(max_length=100, blank=True, default='')  # PERSONAL_MOBILE

    extranet = models.BooleanField(default=None, null=True)

    is_admin = models.BooleanField(blank=True, default=False)

    user_created = models.DateTimeField(null=True, default=timezone.now)

    user_is_active = models.BooleanField(default=True)  # ACTIVE

    def __str__(self):
        return "#{} {} {} bx_id={}".format(self.pk, self.last_name, self.first_name, self.bitrix_id)

    def update_from_bitrix_response(self, user, save=True):
        """Принимает словарь - данные пользователя от user.get/user.current
        и обновляет данные этого (self) пользователя
        """

        if self.bitrix_id is None:
            self.bitrix_id = int(user['ID'])
        elif int(self.bitrix_id) != int(user['ID']):
            t = 'User mismatch: local #{self.bitrix_id} user_info#{info[ID]}'
            raise RuntimeError(t.format(self=self, info=user))

        def _f(field_name, default='', max_length=255):
            value = user.get(field_name) or default
            if max_length is not None:
                value = str(value)[:max_length]
            return value

        # Обновление основных полей
        self.first_name = _f('NAME')
        self.last_name = _f('LAST_NAME')
        self.email = _f('EMAIL')

        self.work_phone = _f('WORK_PHONE', max_length=100)
        self.personal_mobile = _f('PERSONAL_MOBILE', max_length=100)

        self.linkedin = _f('UF_LINKEDIN')
        self.facebook = _f('UF_FACEBOOK')
        self.twitter = _f('UF_TWITTER')
        self.skype = _f('UF_SKYPE')

        if save:
            self.save()

    @classmethod
    def update_portal_staff(cls):
        """
        Метод обновит user_is_active для всех BitrixUser на основе user.get.
        :return: (число активных BitrixUser, число неактивных BitrixUser)
        """
        from integration_utils.bitrix24.models import BitrixUserToken
        admin_token = BitrixUserToken.get_random_token(is_admin=True)
        active_users = [item['ID'] for item in admin_token.call_list_fast('user.get', {"filter": {"ACTIVE": True}})]
        return (cls.objects.filter(bitrix_id__in=active_users).update(user_is_active=True),
                cls.objects.exclude(bitrix_id__in=active_users).update(user_is_active=False))

    def update_is_admin(self, bx_user_token: 'BitrixUserToken', save=True, save_is_admin=True, save_is_active=False, fail_silently=True):
        """
        Узнать от Битрикс, активный ли пользователь и админ ли он.
        Обновляет поля is_admin и user_is_active у пользователя.

        :param bx_user_token: токен пользователя
        :param save: сохранить в БД
        :param save_is_admin: сохранить в БД статус админа
        :param save_is_active: сохранить в БД статус активности
        :param fail_silently: при ошибке делаем лог, если True; кидаем исключение, если False
        :raise BitrixApiException: ошибки API Битрикс
        :raise Exception: иные ошибки функции
        """
        log_tag = 'integration_utils.BitrixUser.update_is_admin'

        def handle_exception(exc, log_function, log_type):
            if fail_silently:
                log_function(log_type, f"({exc}): user={self}, token={bx_user_token}", tag=log_tag, exc_info=True)
            else:
                raise exc

        def handle_bitrix_exception(exc, log_type):
            log_function = ilogger.warning if exc.is_not_logic_error else ilogger.error
            handle_exception(exc, log_function, log_type)

        if bx_user_token.user_id != self.id:
            e = Exception("token doesn't match user")
            handle_exception(e, ilogger.error, 'token_mismatch')
            return

        is_active = True
        is_admin = False

        # Если не внешний пользователь
        if self.bitrix_id > 0:
            is_active = self.user_is_active
            is_admin = self.is_admin

            try:
                is_admin = bx_user_token.call_api_method('user.admin', timeout=(3.05, 10))['result']
            except BitrixApiError as e:
                if e.error_description in [
                    'Unable to authorize user',
                    "Current user can't be authorized in this context",
                ]:
                    # Вероятно, пользователь уволен на портале
                    is_active = False
                    ilogger.debug('is_admin_user_likely_inactive', f"({e}): user={self}, token={bx_user_token}", tag=log_tag)
                else:
                    handle_bitrix_exception(e, 'is_admin_bitrix_api_error')
                    return
            except BitrixApiException as e:
                handle_bitrix_exception(e, 'is_admin_bitrix_api_exception')
                return

            if not isinstance(is_admin, bool):
                e = Exception(f"user.admin returned {is_admin!r} instead of bool")
                handle_exception(e, ilogger.error, 'is_admin_not_bool')
                return

        self.user_is_active = is_active
        self.is_admin = is_admin

        if save:
            update_fields = []
            if save_is_admin:
                update_fields.extend(['is_admin'])
            if save_is_active:
                update_fields.extend(['user_is_active'])
            self.save(update_fields=update_fields)
