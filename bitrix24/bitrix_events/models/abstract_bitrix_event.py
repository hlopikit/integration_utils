from typing import Any, Dict

from dateutil.parser import isoparse
from django.db import models
from django.utils import timezone

from ..classes import BitrixEvent


class AbstractBitrixEvent(BitrixEvent, models.Model):
    """Абстрактный класс события Bitrix24."""

    bitrix_id = models.CharField(max_length=255, unique=True)
    event_name = models.CharField(max_length=127, default='', db_index=True)
    data = models.JSONField(default=dict)
    datetime = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True
        verbose_name = 'Событие'
        verbose_name_plural = 'События'

    def __init__(self, *args, **kwargs):
        """Инициализирует Django-модель без вызова конструктора BitrixEvent."""
        models.Model.__init__(self, *args, **kwargs)

    def __str__(self) -> str:
        return '[{}] {}'.format(self.pk, self.event_name)

    @classmethod
    def from_bitrix_data(cls, data: Dict[str, Any]) -> "AbstractBitrixEvent":
        event, _ = cls.objects.get_or_create(
            bitrix_id=data['ID'],
            defaults={
                'event_name': data['EVENT_NAME'],
                'data': data,
                'datetime': isoparse(data['TIMESTAMP_X']),
            },
        )
        return event
