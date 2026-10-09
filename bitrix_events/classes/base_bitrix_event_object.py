from datetime import datetime
from typing import Any, Dict, Optional

from dateutil.parser import isoparse


class BaseBitrixEventObject:
    """Событие Bitrix24"""

    def __init__(self, event_name: str, datetime: datetime, data: Optional[Dict[str, Any]] = None):
        self.event_name = event_name
        self.data = data if data is not None else {}
        self.datetime = datetime

    def process(self) -> Any:
        """Вызывает <event_name>_handler; исключения передаются вызывающему коду"""
        handler = getattr(self, '{}_handler'.format(self.event_name.lower()), None)
        if handler is None:
            raise NotImplementedError('Handler for {} is not implemented'.format(self.event_name))
        return handler()

    @classmethod
    def from_bitrix_data(cls, data: Dict[str, Any]) -> "BaseBitrixEventObject":
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
