# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from functools import reduce

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils import timezone
import six
import settings
from ones_with_bitrix24.functions.odata_request import OdataRequests

if False:
    from bitrix_utils.bitrix_auth.models import BitrixUserToken
else:
    from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken

if not six.PY2:
    from typing import Optional, Sequence


@six.python_2_unicode_compatible
class BitrixEvent(models.Model):
    """Оффлайн-событие, полученное от Б24
    """
    # portal = models.ForeignKey('bitrix_auth.BitrixPortal', on_delete=models.CASCADE)
    event_name = models.CharField(max_length=127, default='')
    data = JSONField(default=dict)
    datetime = models.DateTimeField(default=timezone.now)

    # bitrix_id = models.IntegerField(null=True, blank=True)

    from its_utils.django_postgres_fuzzycount.fuzzycount import FuzzyCountManager
    objects = FuzzyCountManager()

    class Meta:
        verbose_name = 'Событие'
        verbose_name_plural = 'События'

    def __str__(self):
        return '[{}][{}] {}'.format(self.portal, self.id, self.event_name)

    def get_token(self, application_names, is_admin=None, using=None):
        # type: (Sequence[str], Optional[bool], Optional[str]) -> Optional[BitrixUserToken]
        """Возвращает токен для запросов к api

        application_names: подходящие коды приложения, например: 'itsolutionru.kdb'
        is_admin: админский ли нужен токен? None - не важно какой
        using: https://docs.djangoproject.com/en/3.0/topics/db/multi-db/#manually-selecting-a-database-for-a-queryset
        """
        return self.portal.random_token(
            application_names=application_names,
            is_admin=is_admin,
            using=using,
        )

    def user_id(self):  # type: () -> Optional[int]
        """Пользователь, инициировавший событие передается
        в EVENT_ADDITIONAL['user_id']

        NB! соответствует BitrixUser.bitrix_id пользователя
        """
        if self.event_name.upper() == 'ONUSERADD':
            # Событие добавления пользователя по факту срабатывает,
            # когда новый пользователь заходит на портал, так что можно считать
            # это событием "подтверждением регистрации" от нового пользователя.
            # В этом случае он сам является инициатором действия, а не тот
            # человек, который пригласил его на портал
            return int(self.data['EVENT_DATA']['ID'])

        user_id_paths = (
            ['EVENT_DATA', 'USER_ID'],
            ['EVENT_DATA', 'PORTAL_USER_ID'],
            ['EVENT_ADDITIONAL', 'user_id'],
        )
        for path in user_id_paths:
            try:
                user_id = int(reduce(dict.__getitem__, path, self.data))
                break
            except (KeyError, TypeError, ValueError):
                pass
        else:
            return

        if user_id == 0:
            # У некоторых событий бывает вот такая хрень
            return 0
        elif user_id:
            return int(user_id)
    user_id.short_description = 'bitrix_id пользователя'
    user_id = property(user_id)

    def save(self, *args, **kwargs):
        event_type = self.event_name

        if event_type in ["ONCRMCOMPANYADD", "ONCRMCOMPANYUPDATE"]:
            if 'EVENT_DATA' in self.data and 'FIELDS' in self.data['EVENT_DATA'] and 'ID' in self.data['EVENT_DATA']['FIELDS']:
                company_id = self.data['EVENT_DATA']['FIELDS']['ID']
                bx_token = BitrixUserToken.objects.get(user__email='evg@it-solution.ru')
                response = bx_token.call_api_method_v2('crm.company.get', {
                    'id': company_id
                })
                company = response['result']
                if company['TITLE'].startswith('ТЕСТ'):
                    if 'UF_CRM_ITS_ONE_S_REF' in company and company['UF_CRM_ITS_ONE_S_REF']:
                        odata_requests = OdataRequests(settings.ONES_USER, settings.ONES_PASSWORD)
                        response = odata_requests.get(
                            "Catalog_Партнеры(guid'" + company['UF_CRM_ITS_ONE_S_REF'] + "')",
                            params={
                                '$format': 'json'
                            }
                        ).json()
                        if response['Description'] != company['TITLE']:
                            odata_requests.patch(
                                "Catalog_Партнеры(guid'" + company['UF_CRM_ITS_ONE_S_REF'] + "')",
                                params={'$format': 'json'},
                                json={'Description': company['TITLE']}
                            )

        super().save(*args, **kwargs)
