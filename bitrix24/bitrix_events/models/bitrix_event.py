from typing import Any, Dict

from dateutil.parser import isoparse
from django.db import models
from django.utils import timezone

from ..bitrix_event import BitrixEvent


class AbstractBitrixEvent(BitrixEvent, models.Model):
    """Абстрактный класс события Bitrix24."""

    event_name = models.CharField(max_length=127, default='', db_index=True)
    data = models.JSONField(default=dict)
    datetime = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True
        verbose_name = 'Событие'
        verbose_name_plural = 'События'

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)

    def __str__(self) -> str:
        return '[{}] {}'.format(self.pk, self.event_name)

    @classmethod
    def from_bitrix_data(cls, data: Dict[str, Any]) -> "AbstractBitrixEvent":
        return cls.objects.create(
            event_name=data['EVENT_NAME'],
            data=data,
            datetime=isoparse(data['TIMESTAMP_X']),
        )
