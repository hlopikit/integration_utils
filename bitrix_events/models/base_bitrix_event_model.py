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

    PROCESS_WHEN_RECEIVED = False
    '''
    Обрабатывать ли событие в момент получения.
    Для модельного события можно ставить и True, и False.
    True - для обработки внутри collect_offline_events.
    False - для обработки в отдельном process_offline_events.
    '''

    bitrix_id = models.CharField(max_length=255, unique=True)
    event_name = models.CharField(max_length=127, default='', db_index=True)
    data = models.JSONField(default=dict)
    datetime = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    process_started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    process_ended_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        abstract = True

    class Admin(admin.ModelAdmin):
        list_display = [
            'bitrix_id', 'event_name', 'data', 'datetime', 'created_at',
            'process_started_at', 'process_ended_at',
        ]
        list_display_links = list_display
        readonly_fields = ['created_at', 'process_started_at', 'process_ended_at']

    def __init__(self, *args, **kwargs):
        """Инициализирует Django-модель без конструктора BaseBitrixEventObject"""
        models.Model.__init__(self, *args, **kwargs)

    def __str__(self) -> str:
        return f'[{self.pk}] {self.event_name}'

    def process(self) -> Any:
        """Обработать событие"""
        return self.process_with_lock()

    def process_with_lock(self, force: bool = False) -> Any:
        """
        Обработать событие с блокировкой.
        :param force: запустить обработку независимо от блокировки.
        """
        if not force and (self.process_started_at or self.process_ended_at):
            return None

        process_started_at = timezone.now()
        event_qs = type(self).objects.filter(pk=self.pk)
        if force:
            updated = event_qs.update(
                process_started_at=process_started_at,
                process_ended_at=None,
            )
        else:
            updated = event_qs.filter(
                process_started_at__isnull=True,
                process_ended_at__isnull=True,
            ).update(
                process_started_at=process_started_at,
            )

        if not updated:
            return None

        self.process_started_at = process_started_at
        self.process_ended_at = None
        try:
            return super().process()
        finally:
            process_ended_at = timezone.now()
            event_qs.update(process_ended_at=process_ended_at)
            self.process_ended_at = process_ended_at

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
