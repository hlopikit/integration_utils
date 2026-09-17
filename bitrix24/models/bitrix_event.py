from typing import Any

from django.db import models
from django.utils import timezone


class AbstractBitrixEvent(models.Model):
    """Абстрактный класс события Bitrix24."""

    event_name = models.CharField(max_length=127, default='', db_index=True)
    data = models.JSONField(default=dict)
    datetime = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True
        verbose_name = 'Событие'
        verbose_name_plural = 'События'

    def __str__(self) -> str:
        return '[{}] {}'.format(self.pk, self.event_name)

    def process(self) -> Any:
        """Вызывает обработчик события; события без обработчика пропускаются.

        Исключения обработчика передаются вызывающему коду.
        """
        event_name = self.event_name.lower()
        if event_name.startswith('on'):
            event_name = event_name[2:]
        handler = getattr(self, 'on_{}'.format(event_name), None)
        if handler is not None:
            return handler()
        return None
