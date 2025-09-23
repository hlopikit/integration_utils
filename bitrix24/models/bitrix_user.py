from django.db import models
from django.utils import timezone

from integration_utils.bitrix24.exceptions import BitrixApiError
from settings import ilogger


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
        return "#{} {} {}".format(self.pk, self.last_name, self.first_name)

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
        # метод пометит всем сотрудникам портала user_is_active = Тру
        # всем не сотрудникам или не актиным Фалс
        from crm.functions.get_token import get_super_token
        active_users = [item['ID'] for item in get_super_token().call_list_fast('user.get', {"filter":{"ACTIVE":True}})]
        return (cls.objects.filter(bitrix_id__in=active_users).update(user_is_active=True),
                cls.objects.exclude(bitrix_id__in=active_users).update(user_is_active=False))

    def update_is_admin(self, bx_user_token, save=True, save_is_admin=True, save_is_active=False):
        """
        Узнать от Битрикс, активный ли пользователь и админ ли он,
        установить поле is_admin и user_is_active у пользователя.

        :param bx_user_token: токен пользователя
        :param save: сохранить в БД
        :param save_is_admin: сохранить в БД статус админа
        :param save_is_active: сохранить в БД статус активности
        """

        is_active = True
        is_admin = False

        # Если не внешний пользователь
        if self.bitrix_id > 0:
            is_active = self.user_is_active
            is_admin = self.is_admin
            try:
                is_admin = bx_user_token.call_api_method('user.admin')['result']
            except BitrixApiError as e:
                if e.error_description == 'Unable to authorize user':
                    # Возможно, что пользователь уволен на портале
                    is_active = False
                    ilogger.debug('unable_to_authorize_user', 'BitrixUser {}: {}'.format(self.id, repr(e)))
                else:
                    raise e
            if not isinstance(is_admin, bool):
                raise ValueError('user.admin did not return bool: {}'.format(repr(is_admin)))

        self.user_is_active = is_active
        self.is_admin = is_admin

        if save:
            update_fields = []
            if save_is_admin:
                update_fields.extend(['is_admin'])
            if save_is_active:
                update_fields.extend(['user_is_active'])
            self.save(update_fields=update_fields)
