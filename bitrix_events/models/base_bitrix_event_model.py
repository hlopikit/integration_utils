from typing import Any, Dict

from dateutil.parser import isoparse
from django.contrib import admin
from django.db import models
from django.utils import timezone

from ..classes import BaseBitrixEventObject


class BaseBitrixEventModel(BaseBitrixEventObject, models.Model):
    """
    Абстрактная Django-модель для события Битрикс24.
    """

    bitrix_id = models.CharField(max_length=255, unique=True)
    event_name = models.CharField(max_length=127, default='', db_index=True)
    data = models.JSONField(default=dict)
    datetime = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True

    class Admin(admin.ModelAdmin):
        list_display = ['bitrix_id', 'event_name', 'data', 'datetime']
        list_display_links = list_display

    def __init__(self, *args, **kwargs):
        """Инициализирует Django-модель без конструктора BaseBitrixEventObject"""
        models.Model.__init__(self, *args, **kwargs)

    def __str__(self) -> str:
        return f'[{self.pk}] {self.event_name}'

    @classmethod
    def from_bitrix_data(cls, data: Dict[str, Any]) -> "BaseBitrixEventModel":
        """Создать или получить объект события в БД из словаря с Битрикс-данными"""
        event, _ = cls.objects.get_or_create(
            bitrix_id=data['ID'],
            defaults={
                'event_name': data['EVENT_NAME'],
                'data': data,
                'datetime': isoparse(data['TIMESTAMP_X']),
            },
        )
        return event
