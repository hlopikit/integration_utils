from datetime import datetime as dt
from typing import Any, Dict, Optional

from dateutil.parser import isoparse


class BaseBitrixEventObject:
    """
    Базовый класс для события Битрикс24.
    Для обработки события через process нужно добавить handler-метод.
    """

    def __init__(self, event_name: str, datetime: dt, data: Optional[Dict[str, Any]] = None):
        self.event_name = event_name
        self.data = data if data is not None else {}
        self.datetime = datetime

    def process(self) -> Any:
        """Вызывает метод-обработчик по имени события"""
        handler = getattr(self, f'{self.event_name.lower()}_handler', None)
        if handler is None:
            raise NotImplementedError(f'Handler for {self.event_name} is not implemented')
        return handler()

    @classmethod
    def from_bitrix_data(cls, data: Dict[str, Any]) -> "BaseBitrixEventObject":
        """Создать объект события из словаря с Битрикс-данными"""
        return cls(
            event_name=data['EVENT_NAME'],
            data=data,
            datetime=isoparse(data['TIMESTAMP_X']),
        )

    @classmethod
    def collect_bitrix_events(cls) -> str:
        """Собрать новую пачку событий"""
        from ..crons.cron_collect_bitrix_events import collect_bitrix_events
        return collect_bitrix_events(cls)
