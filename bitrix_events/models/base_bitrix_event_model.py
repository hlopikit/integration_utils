from datetime import datetime
from typing import Any, Dict, Literal, overload

from django.contrib import admin
from django.db import models
from django.utils import timezone

from ..classes import BaseBitrixEventObject
from ..functions.offline_events import collect_offline_events, process_offline_events


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
    success = models.BooleanField(null=True, blank=True, default=None, db_index=True)
    error = models.TextField(null=True, blank=True, default=None)

    class Meta:
        abstract = True

    class Admin(admin.ModelAdmin):
        list_display = 'bitrix_id', 'event_name', 'data', 'datetime', 'created_at', 'process_started_at', 'process_ended_at', 'success', 'error'
        list_display_links = list_display
        readonly_fields = 'created_at', 'process_started_at', 'process_ended_at', 'success', 'error'

    def __init__(self, *args, **kwargs):
        """
        Инициализирует Django-модель без конструктора BaseBitrixEventObject.
        """
        models.Model.__init__(self, *args, **kwargs)

    def __str__(self) -> str:
        return f'[{self.pk}] {self.event_name}'

    def process(self) -> Any:
        """
        Обработать событие.
        """
        return self.process_with_lock()

    def process_with_lock(self, force: bool = False) -> Any:
        """
        Обработать событие с блокировкой.
        При успехе записать success=True, при исключении - success=False и текст ошибки.
        :param force: запустить обработку независимо от блокировки.
        """

        if not force and (self.process_started_at or self.process_ended_at):
            return None

        process_started_at = timezone.now()
        event_qs = type(self).objects.filter(pk=self.pk)

        if force:
            started = event_qs.update(
                process_started_at=process_started_at,
                process_ended_at=None,
                success=None,
                error=None,
            )
        else:
            started = event_qs.filter(
                process_started_at__isnull=True,
                process_ended_at__isnull=True,
            ).update(
                process_started_at=process_started_at,
                success=None,
                error=None,
            )

        if not started:
            return None

        self.process_started_at = process_started_at
        self.process_ended_at = None
        self.success = None
        self.error = None

        success = False
        error = None

        try:
            process_result = super().process()
        except Exception as e:
            error = f'{type(e).__name__}({e})'
            raise
        else:
            success = True
            return process_result
        finally:
            process_ended_at = timezone.now()

            ended = event_qs.filter(
                process_started_at=process_started_at
            ).update(
                process_ended_at=process_ended_at,
                success=success,
                error=error,
            )

            if ended:
                self.process_ended_at = process_ended_at
                self.success = success
                self.error = error

    @classmethod
    def from_bitrix_data(cls, data: Dict[str, Any]) -> "BaseBitrixEventModel":
        """
        Создать или получить объект события в БД из словаря с Битрикс-данными.
        """

        event, _ = cls.objects.get_or_create(
            bitrix_id=data['ID'],
            defaults={
                'event_name': data['EVENT_NAME'],
                'data': data,
                'datetime': datetime.fromisoformat(data['TIMESTAMP_X']),
            },
        )

        return event

    @classmethod
    @overload
    def make_cron_collect_offline_events(
        cls,
        *,
        clear_on_get: Literal[False] = False,
        clear_error: Literal[True] = True,
        recover: bool = False,
    ) -> str:
        """
        Собираем события без очистки при сборе, с пометкой ошибок в очереди.
        Параметр recover можно ставить любой.
        """

    @classmethod
    @overload
    def make_cron_collect_offline_events(
        cls,
        *,
        clear_on_get: Literal[False] = False,
        clear_error: Literal[False],
        recover: Literal[True],
    ) -> str:
        """
        Собираем события без очистки при сборе, без пометки ошибок в очереди.
        Параметр recover нужно ставить True, чтобы дособрать ошибки из очереди.
        """

    @classmethod
    @overload
    def make_cron_collect_offline_events(
        cls,
        *,
        clear_on_get: Literal[True],
        clear_error: Literal[False] = False,
        recover: Literal[False] = False,
    ) -> str:
        """
        Собираем события с очисткой при сборе.
        Параметры recover и clear_error использоваться не будут, поэтому False.
        """

    @classmethod
    def make_cron_collect_offline_events(cls, clear_on_get: bool = False, clear_error: bool = True, recover: bool = False):
        def cron_collect_offline_events():
            return collect_offline_events(cls, clear_on_get=clear_on_get, clear_error=clear_error, recover=recover)
        return cron_collect_offline_events

    @classmethod
    def make_cron_process_offline_events(cls, limit: int = 50):
        def cron_process_offline_events():
            return process_offline_events(cls, limit=limit)
        return cron_process_offline_events
